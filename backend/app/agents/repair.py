"""Repair agent — generative bug-fix via an optional LLM.

The repair agent is the generative counterpart to the skill playbooks. When no
registered skill matches and an LLM backend is configured (``FORGE_LLM_ENABLED``),
it proposes an actual code change against FORGE's *real* root-cause evidence:
mission text, debugger findings + call-chain, and any failing test rows.

Honesty rules:
  * The model may only propose edits to real files that exist in the mission
    workspace; content is applied to the workspace copy, never the pristine repo.
  * A proposal is NOT a committed change. The pipeline runs the real validation
    suite against the proposal and only records it as a change (with its diff)
    when the tests actually pass. If validation fails, the proposal is reverted.
  * If the LLM is unavailable or returns nothing usable, the agent says so.
"""

from __future__ import annotations

from pathlib import Path

from .. import config
from ..intel import workspace as ws
from ..llm import LLMError, chat_json
from .base import Timer

_SYSTEM = (
    "You are FORGE's repair engineer. You are given real evidence about a defect "
    "(mission text, root-cause findings with file:line references, failing tests, "
    "and the current contents of specific files in a repository). "
    "Propose the minimal, correct code fix to make the failing tests pass. "
    'Respond with ONLY a JSON object in this exact shape:\n'
    '{"files": [{"path": "<relative path from repo root>", "new_content": "<COMPLETE new file content>"}]}\n'
    "Rules: new_content must be the ENTIRE new file; never omit sections you did not change. "
    "Only edit files from the provided list. Do not add tests. Do not include markdown fences. "
    "Be conservative: change the smallest amount needed to fix the defect."
)


def _rollup_tests(tester_payload: dict) -> list[str]:
    rows = (tester_payload.get("result", {}) or {}).get("tests", []) or []
    failing = [r for r in rows if r.get("status") in ("failed", "pending")]
    out = []
    for r in failing:
        out.append(f"{r.get('path', '?')} :: {r.get('name', '?')}")
    return out


def _resolve_specifier(root: Path, from_rel: str, spec: str) -> str | None:
    """Resolve a relative import to an existing file in the repo."""
    if not spec.startswith("."):
        return None
    import posixpath
    base = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), spec))
    candidates = [base, base + ".ts", base + ".tsx", base + ".js", base + ".jsx", base + ".py"]
    for cand in candidates:
        p = root / cand
        if p.is_file():
            return cand
    return None


def _import_neighbors(root: Path, test_rel: str) -> list[str]:
    """Files imported by a failing test — the likely fix targets."""
    import re
    out: list[str] = []
    try:
        text = (root / test_rel).read_text(encoding="utf-8")
    except OSError:
        return out
    for m in re.finditer(r'(?:from\s+|import\s+)["\']([^"\']+)["\']', text):
        resolved = _resolve_specifier(root, test_rel, m.group(1))
        if resolved and resolved not in out:
            out.append(resolved)
    for m in re.finditer(r'from\s+([\.\w]+)\s+import', text):
        pass  # relative (dotted) specifiers: `from .util import x`
    dotted = re.findall(r'from\s+(\.[\.\w]+)\s+import', text)
    for spec in dotted:
        resolved = _resolve_specifier(root, test_rel, spec)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


def _evidence_files(ctx: dict, debugger_payload: dict, tester_payload: dict) -> list[str]:
    import posixpath
    root: Path = Path(ctx["root"])
    picks: list[str] = []
    dbg = debugger_payload.get("result", {}) or {}
    for c in dbg.get("root_cause_candidates", []):
        for f in c.get("affected_files", []) or []:
            if f:
                picks.append(f)
    for f in debugger_payload.get("affected_files", []) or []:
        picks.append(f)
    for t in tester_payload.get("result", {}).get("tests", []) or []:
        path = t.get("path", "")
        if not path:
            continue
        picks.append(path)
        if t.get("status") in ("failed", "pending"):
            picks.extend(_import_neighbors(root, path))
    uniq = []
    for f in picks:
        if not f:
            continue
        rel = posixpath.normpath(f.lstrip("/"))
        if rel and rel not in uniq:
            uniq.append(rel)
    return uniq[: config.LLM_MAX_FILES]


def run_repair(ctx: dict, debugger_payload: dict, tester_payload: dict) -> dict:
    with Timer() as timer:
        root: Path = Path(ctx["root"])
        pristine: Path = Path(ctx["pristine"])
        picked = _evidence_files(ctx, debugger_payload, tester_payload)
        selected: list[str] = []
        sections: list[str] = []

        for rel in picked:
            p = root / rel
            if not p.is_file():
                continue
            try:
                content = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if not ws.rel_file(root, rel).is_relative_to(ws.rel_file(root, ".")):
                continue
            if len(content.encode("utf-8")) > config.LLM_MAX_FILE_BYTES:
                continue
            selected.append(rel)
            sections.append(f"### {rel}\n```\n{content}\n```")

        dbg = debugger_payload.get("result", {}) or {}
        candidates = dbg.get("root_cause_candidates", []) or []
        candidate_text = "\n".join(
            f"- [{c.get('rank', '?')}] {c.get('title', '')} (confidence {c.get('confidence', 0)}) in {c.get('component', '?')}"
            for c in candidates
        ) or "No debugger root-cause hypothesis was produced."

        user_parts = [
            f"MISSION: {ctx.get('mission_text', '(no mission text provided)')}",
            f"ROOT-CAUSE EVIDENCE:\n{candidate_text}",
            f"FAILING TESTS:\n" + ("\n".join(_rollup_tests(tester_payload)) or "none captured"),
            f"FILES TO EDIT (paths are relative to repo root):\n{' '.join(selected) or 'none'}\n",
        ]
        if sections:
            user_parts.append("CURRENT FILE CONTENTS (edit these only):\n\n" + "\n\n".join(sections))

        proposed: list[dict] = []
        findings: list[dict] = []
        error = "LLM returned no usable edits for the selected files."
        if not selected:
            error = "No applicable source files found to edit — cannot propose a repair."
        else:
            try:
                data = chat_json(
                    [{"role": "system", "content": _SYSTEM},
                     {"role": "user", "content": "\n\n".join(user_parts)}],
                    temperature=0.1,
                )
                for item in data.get("files", []) or []:
                    rel = str(item.get("path", "")).strip().lstrip("/")
                    content = item.get("new_content")
                    if not isinstance(content, str) or not rel:
                        continue
                    import posixpath
                    rel = posixpath.normpath(rel)
                    if rel not in selected:
                        continue
                    ws.write_text(root, rel, content)
                    proposed.append({"path": rel, "content": content})
            except LLMError as exc:
                error = f"LLM unavailable: {exc}"
            if not proposed:
                error = "LLM returned no usable edits for the selected files."

        if proposed:
            summary = f"AI repair proposed edits to {len(proposed)} file(s) for verification: {', '.join(p['path'] for p in proposed)}."
            findings = [{
                "agent": "repair", "title": f"Generative repair proposed for {len(proposed)} file(s)",
                "detail": "An LLM proposed edits based on FORGE's evidence. The pipeline verifies them with the real validation suite before committing.",
                "severity": "info", "category": "implementation",
                "file": proposed[0]["path"], "line": None, "confidence": 0.5,
                "evidence_refs": ["llm-call"],
            }]
        else:
            summary = f"AI repair unavailable: {error}"
            findings = [{
                "agent": "repair", "title": "AI repair could not propose a verified change",
                "detail": error, "severity": "low", "category": "implementation",
                "file": "", "line": None, "confidence": 0.0, "evidence_refs": [],
            }]

        evidence = [{
            "agent": "repair", "kind": "llm",
            "label": f"Generative repair call ({config.LLM_BASE_URL}, model {config.LLM_MODEL})",
            "source": "llm", "payload": {"provider": config.LLM_BASE_URL, "model": config.LLM_MODEL,
                                          "files_included": selected, "files_proposed": [p["path"] for p in proposed],
                                          "result": str(data)[:400] if "data" in locals() else ""},
        }]

    return {
        "status": "completed", "summary": summary,
        "result": {"proposed": proposed, "files": [p["path"] for p in proposed]},
        "findings": findings, "evidence": evidence,
        "affected_files": [p["path"] for p in proposed],
        "recommendations": ["Validation must pass for the proposal to be committed."] if proposed else [],
        "confidence": 0.5 if proposed else 0.0, "duration_ms": timer.elapsed_ms,
    }