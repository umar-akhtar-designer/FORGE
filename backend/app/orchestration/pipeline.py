"""Mission pipeline — orchestrates the full engineering workflow.

Stages mirror the FORGE blueprint. Investigation agents run concurrently;
everything is recorded to the evidence store with real timings.

The pipeline is repository-agnostic: the skill registry drives which defect
playbook the debugger probes, which patches the actor applies, and which
regression the tester writes. A repository without a matching skill still
gets indexed, planned, investigated, validated and release-gated — it just
produces no autonomous fix.
"""

from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import config, store
from ..agents import actor as actor_agent
from ..agents import architect as architect_agent
from ..agents import base as base_agent
from ..agents import critic as critic_agent
from ..agents import debugger as debugger_agent
from ..agents import release as release_agent
from ..agents import repair as repair_agent
from ..agents import security as security_agent
from ..agents import tester as tester_agent
from ..intel import workspace as ws
from ..intel.indexer import architecture_map, component_of, dependencies_manifest, index_directory
from ..skills.learn import learn_from_mission
from ..skills import matched as match_skills
from . import metrics as metrics_builder

STEPS = [
    ("init", "Repository connected"),
    ("index", "Architecture indexed"),
    ("plan", "Investigation plan generated"),
    ("investigate", "Parallel agent investigation"),
    ("root_cause", "Root cause isolated"),
    ("implement", "Implementation"),
    ("validate", "Validation suite"),
    ("critic", "Actor/Critic review"),
    ("release", "Release gate"),
    ("report", "Evidence report"),
]

_STEP_MESSAGES = {
    "init": "Mission initialized; workspace provisioned.",
    "index": "Repository indexed: architecture mapped.",
    "plan": "Agent team assembled; investigation scope set.",
    "investigate": "Four investigators ran in parallel on the mission workspace.",
    "root_cause": "Root-cause candidate isolated with evidence.",
    "implement": "Approved fix applied to the mission workspace.",
    "validate": "Full suite + typecheck executed on the changed workspace.",
    "critic": "Independent critic review complete.",
    "release": "Release-gate evaluation complete.",
    "report": "Evidence report and impact metrics generated.",
}


def _normalize_findings(agent_name: str, items: list[dict]) -> list[dict]:
    out = []
    for f in items or []:
        out.append({
            "agent": agent_name,
            "title": f.get("title", ""),
            "detail": f.get("detail", ""),
            "severity": f.get("severity", "info"),
            "category": f.get("category", "agent"),
            "file": f.get("file") or f.get("path", ""),
            "line": f.get("line"),
            "confidence": f.get("confidence", 0.0),
            "evidence_refs": f.get("evidence_refs", []),
        })
    return out


def _record_agent(mission_id: str, name: str, order: int, payload: dict) -> None:
    role = base_agent.AGENT_ROLES.get(name, name)
    payload = dict(payload)
    payload["findings"] = _normalize_findings(name, payload.get("findings", []))
    rid = store.add_agent(mission_id, name, role, order)
    store.set_agent_running(rid)
    store.complete_agent(rid, payload)

    for f in payload["findings"]:
        store.add_finding(mission_id, name, f["title"], f.get("detail", ""), f.get("severity", "info"), f.get("category", ""), f.get("file", ""), f.get("line"), f.get("confidence", 0.0), f.get("evidence_refs", []))
    for e in payload.get("evidence", []):
        store.add_evidence(mission_id, name, e["kind"], e["label"], e.get("source", ""), e.get("payload", {}))
    store.add_audit(mission_id, name, "agent", payload.get("summary", ""))


def _record_tests(mission_id: str, phase_key: str, rows: list[dict]) -> None:
    for t in rows:
        store.add_test(mission_id, phase_key, phase_key, t.get("path", ""), t.get("name", ""), t.get("status", "passed"), 0)


def _record_security_findings(mission_id: str, items: list[dict]) -> None:
    for f in items:
        store.add_security_finding(mission_id, f.get("rule", "scan"), f.get("severity", "info"), f.get("title", ""), f.get("path", ""), f.get("line"), f.get("description", ""), f.get("remediation", ""))


def _repo_root(repo_name: str) -> Path:
    """Resolve the pristine repository root (bundled demo or an uploaded repo)."""
    idx = store.get_repository_index(repo_name)
    if idx and idx.path:
        p = Path(idx.path)
        if p.is_dir():
            return p
    return config.FORGEMART_DIR


def run_mission(mission_id: str, mission_text: str, demo_seed: int, repo_name: str = "forgemart") -> None:
    run_started = time.perf_counter()
    run_log: dict = {}

    try:
        pristine = _repo_root(repo_name)
        mission = store.get_mission(mission_id)
        if mission is None:
            return

        for i, (stage, name) in enumerate(STEPS):
            store.add_step(mission_id, stage, name, "pending", "", i)
        steps = store.get_steps(mission_id)
        step_ids = {s.stage: s.id for s in steps}

        def mark(stage: str, status: str, message: str = "") -> None:
            sid = step_ids.get(stage)
            if sid is not None:
                store.set_step_status(sid, status, message or _STEP_MESSAGES.get(stage, ""))

        mark("init", "running")

        root = ws.create_workspace(mission_id, pristine)
        store.start_mission(mission_id, str(root))

        index_data = index_directory(pristine)
        architecture = architecture_map(index_data["files"], index_data["by_path"])
        index_data["architecture"] = architecture
        stats = {
            "files": len(index_data["files"]),
            "lines": sum(f["lines"] for f in index_data["files"]),
            "tests": len(index_data["tests"]),
            "components": len(architecture["components"]),
        }
        run_log["investigated_files"] = set()
        store.save_repository_index(repo_name, str(pristine), stats, index_data["files"], index_data["tests"], architecture, dependencies_manifest(pristine))
        comp_names = ", ".join(c["id"] for c in architecture["components"][:10])
        store.add_audit(mission_id, "system", "index", f"Repository indexed: {stats['files']} files, {stats['lines']} lines, {stats['components']} components, {len(index_data['tests'])} tests. Components: {comp_names}.")
        mark("init", "completed")
        mark("index", "completed")

        # Skill matching is a cheap, real scan over the workspace.
        skill_hits = match_skills(root)
        run_log["skills_matched"] = [s.id for s, _ in skill_hits]
        ctx: dict = {
            "mission_id": mission_id,
            "root": root,
            "pristine": pristine,
            "index": index_data,
            "mission_text": mission_text,
            "seed": demo_seed,
            "skills": [s for s, _ in skill_hits],
            "skill": skill_hits[0][0] if skill_hits else None,
        }
        for s, _ in skill_hits:
            store.add_audit(mission_id, "skill", "matched", f"Skill matched: {s.name} ({s.id})")
        if not skill_hits:
            store.add_audit(mission_id, "system", "skill", "No registered skill matched this repository.")

        mark("plan", "running")
        keywords = architect_agent._keywords_for(mission_text, ctx["skill"])
        store.add_audit(mission_id, "system", "plan", f"Investigation plan generated around {len(keywords)} signals: {', '.join(keywords[:10])}.")
        mark("plan", "completed")

        mark("investigate", "running")
        investigate_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=config.MAX_PARALLEL_INVESTIGATORS) as pool:
            f1 = pool.submit(architect_agent.run_architect, ctx, ctx["skill"])
            f2 = pool.submit(debugger_agent.run_debugger, ctx, ctx["skill"])
            f3 = pool.submit(security_agent.run_security, ctx)
            f4 = pool.submit(tester_agent.run_tester, {**ctx, "phase": "investigate"}, ctx["skill"])
            payloads = [f1.result(), f2.result(), f3.result(), f4.result()]
        run_log["parallel"] = config.MAX_PARALLEL_INVESTIGATORS
        run_log["investigate_duration_ms"] = int((time.perf_counter() - investigate_start) * 1000)

        _record_agent(mission_id, "architect", 0, payloads[0])
        _record_agent(mission_id, "debugger", 1, payloads[1])
        _record_agent(mission_id, "security", 2, payloads[2])
        _record_security_findings(mission_id, payloads[2].get("findings", []))
        _record_agent(mission_id, "tester", 3, payloads[3])
        investigations_ok = all(p["status"] == "completed" for p in payloads)
        mark("investigate", "completed" if investigations_ok else "failed")

        inv_test_rows = payloads[3].get("result", {}).get("tests", [])
        _record_tests(mission_id, "investigate", inv_test_rows)

        mark("root_cause", "running")
        dbg = payloads[1]
        candidates = dbg.get("result", {}).get("root_cause_candidates", [])
        if candidates:
            store.add_audit(mission_id, "debugger", "root-cause", f"Root cause candidate: {candidates[0]['title']} (confidence {candidates[0]['confidence']}).")
        mark("root_cause", "completed")

        mark("implement", "running")
        act = actor_agent.run_actor(ctx, ctx["skill"])
        _record_agent(mission_id, "actor", 4, act)
        changes = act.get("result", {}).get("changes", [])
        for c in changes:
            store.add_code_change(mission_id, c["path"], c["status"], c["added"], c["removed"], c["diff"], c["reason"])
        store.add_audit(mission_id, "actor", "implement", f"Patch applied: {len(changes)} file(s), +{sum(c['added'] for c in changes)} -{sum(c['removed'] for c in changes)} lines.")

        # Generative repair: only when no deterministic skill produced a fix.
        repair_proposals: list[dict] = []
        if not changes and ctx["skill"] is None and config.LLM_ENABLED:
            rep = repair_agent.run_repair(ctx, payloads[1], payloads[3])
            for e in rep.get("evidence", []):
                store.add_evidence(mission_id, "repair", e["kind"], e["label"], e.get("source", ""), e.get("payload", {}))
            for f in rep.get("findings", []):
                store.add_finding(mission_id, "repair", f["title"], f.get("detail", ""), f.get("severity", "info"), f.get("category", ""), f.get("file", ""), f.get("line"), f.get("confidence", 0.0), f.get("evidence_refs", []))
            store.add_audit(mission_id, "repair", "implement", rep["summary"])
            repair_proposals = rep.get("result", {}).get("proposed", [])
        mark("implement", "completed")

        mark("validate", "running")
        t_val = tester_agent.run_tester({**ctx, "phase": "validate"}, ctx["skill"])
        _record_agent(mission_id, "tester", 5, t_val)
        vres = t_val.get("result", {})
        full = vres.get("full", {})
        tc = vres.get("typecheck", {})
        _record_tests(mission_id, "validate", vres.get("tests", []))
        store.add_audit(mission_id, "tester", "validate", f"Validation: {full.get('total', 0)} tests, {full.get('failed', 0)} failed; typecheck exit {tc.get('exit_code', '?')}.")
        run_log["tests_executed"] = full.get("total", 0)
        run_log["tests_generated"] = sum(1 for t in inv_test_rows if "regression" in t.get("path", ""))
        mark("validate", "completed")

        # Generative repair honesty: commit ONLY when real validation passed.
        if repair_proposals:
            verified = bool(full.get("ran")) and full.get("failed", 0) == 0 and (not tc.get("ran") or tc.get("exit_code") == 0)
            if verified:
                commits = []
                for p in repair_proposals:
                    rel = p["path"]
                    before = ws.read_text(pristine, rel)
                    worker_now = ws.read_text(root, rel)
                    diff = ws.unified_diff(pristine, root, rel, before_content=before)
                    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
                    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
                    if worker_now != before:
                        commits.append({"path": rel, "status": "modified", "added": added, "removed": removed,
                                        "diff": diff, "reason": "AI repair (LLM-generated) verified by validation"})
                changes.extend(commits)
                for c in commits:
                    store.add_code_change(mission_id, c["path"], c["status"], c["added"], c["removed"], c["diff"], c["reason"])
                store.add_audit(mission_id, "repair", "verify", f"AI repair verified by validation — {len(commits)} file(s) committed.")
            else:
                for p in repair_proposals:
                    ws.write_text(root, p["path"], ws.read_text(pristine, p["path"]))
                store.add_audit(mission_id, "repair", "revert", "AI repair was not verified by the validation suite — proposal reverted, no change committed.")

        mark("critic", "running")
        diff_blob = "\n".join(c.get("diff", "") for c in changes)
        sec = payloads[2].get("result", {})
        inv_generated = payloads[3].get("result", {}).get("generated", "")
        crit = critic_agent.run_critic({
            **ctx, "diff_blob": diff_blob, "changes": changes,
            "test_results": {"regression_tests_generated": bool(inv_generated), "validate_failed": full.get("failed", 0) if full.get("ran") else -1},
            "security_counts": sec.get("counts", {}),
        }, ctx["skill"])
        _record_agent(mission_id, "critic", 6, crit)
        crit_issues = crit["result"].get("issues", [])
        store.add_review(mission_id, "critic", crit["result"]["verdict"], crit["result"]["score"], crit["summary"],
                         crit_issues or crit["result"].get("checks", []), [c["path"] for c in changes])
        store.add_audit(mission_id, "critic", "critic", f"Critic verdict: {crit['result']['verdict'].upper()} ({crit['result']['score']}%).")
        mark("critic", "completed")

        # Architecture integrity: changes must stay inside the skill's declared
        # components; the display risk is the max real component risk touched.
        changed_comps = {component_of(c["path"]) for c in changes}
        declared = set(ctx["skill"].criteria.get("scope_prefixes", [])) if ctx["skill"] else set()
        arch_ok = bool(changed_comps) and (not declared or changed_comps <= declared)
        comp_risk = {n["id"]: n.get("risk", 0) for n in architecture["components"]}
        arch_risk = max((comp_risk.get(c, 0) for c in changed_comps), default=0)

        mark("release", "running")
        rel = release_agent.run_release({
            "typecheck": {"ran": bool(tc.get("ran")), "ok": tc.get("exit_code") == 0},
            "unit": {"ran": bool(full.get("ran")), "failed": full.get("failed", 0)},
            "regression": {"ran": bool(full.get("ran")) and bool(inv_generated), "failed": full.get("failed", 0)},
            "security_critical": sec.get("counts", {}).get("critical", 99),
            "critic_verdict": crit["result"]["verdict"],
            "architecture": {"ran": bool(changed_comps), "ok": arch_ok, "risk": arch_risk},
            "files_changed": len(changes),
        })
        _record_agent(mission_id, "release", 7, rel)
        for i, ch in enumerate(rel["result"]["checks"]):
            store.add_release_gate(mission_id, ch["name"], ch["status"], ch["detail"], i, rel["result"]["overall"])
        store.add_audit(mission_id, "release", "release", rel["result"]["summary"])
        mark("release", "completed")

        mark("report", "running")
        run_log["duration_ms"] = int((time.perf_counter() - run_started) * 1000)
        run_log["security_rules"] = sec.get("rules", 0)
        run_log["security_files"] = sec.get("files_scanned", 0)
        run_log["security_findings"] = sum(sec.get("counts", {}).values())
        run_log["investigated_files"] |= {e.source for e in store.get_evidence(mission_id) if e.source}
        metrics_builder.compute_and_persist(mission, {"stats": stats}, run_log)
        store.add_audit(mission_id, "system", "report", "Evidence report and impact metrics generated.")
        mark("report", "completed")

        if config.SKILL_LEARNING:
            try:
                learned = learn_from_mission(mission_id)
                if learned:
                    store.add_audit(mission_id, "system", "report", f"Skill learning: registered {len(learned)} learned playbook(s): {', '.join(learned)}.")
            except Exception as exc:  # noqa: BLE001
                store.add_audit(mission_id, "system", "error", f"Skill learning failed (non-fatal): {exc}")

        outcome = "success" if rel["result"]["overall"] == "ready" else "partial"
        store.complete_mission(mission_id, outcome, rel["result"]["summary"], run_log["duration_ms"])
    except Exception as exc:  # noqa: BLE001
        store.add_audit(mission_id, "system", "error", f"Mission failed: {exc}")
        store.set_mission_error(mission_id, f"{exc}\n{traceback.format_exc()[-800:]}")
        raise