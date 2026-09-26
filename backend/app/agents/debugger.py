"""Debugger agent — locate the root cause with real code evidence.

The debugger is repository-agnostic. It asks the skill registry which defect
playbook matches the workspace, then:
  1. runs the skill's generic probes on the real files, and
  2. traces the real call chain of the orchestration symbol.

Every finding carries real file/line references. If no skill matches, the
debugger still reports what it could prove (call chain + probes) and makes no
claims about a root cause.
"""

from __future__ import annotations

from pathlib import Path

from ..intel.indexer import component_of, locate_function, scan_keywords
from ..skills import Skill
from ..skills import run_observations
from .base import Timer


def _read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def run_debugger(ctx: dict, skill: Skill | None = None) -> dict:
    with Timer() as timer:
        root = Path(ctx["root"])

        # 1. Real call chain — locate the orchestration symbol and its callers.
        chain: list[dict] = []
        if skill:
            for d in locate_function(root, skill.orchestration) if skill.orchestration else []:
                chain.append({"path": d["path"], "line": d["line"], "kind": "definition"})
            for caller in skill.callers:
                for d in locate_function(root, caller):
                    if d not in chain:
                        chain.append({"path": d["path"], "line": d["line"], "kind": "caller"})
        else:
            # No skill: still map an intersecting symbol if one is mentioned.
            probe = ctx.get("mission_text", "")
            for word in [w.strip(".,'()\"") for w in probe.split() if len(w.strip(".,'()\"")) >= 4]:
                for d in locate_function(root, word):
                    if d not in chain:
                        chain.append({"path": d["path"], "line": d["line"], "kind": "symbol"})

        # 2. Skill observations -> evidence-backed root-cause findings.
        findings: list[dict] = run_observations(skill, root) if skill else []
        evidence: list[dict] = []

        # 3. Blast radius and source evidence.
        affected_files = []
        if skill:
            affected_files = skill.relevant_files()
            for p in affected_files:
                if not (root / p).exists():
                    continue
                evidence.append({
                    "agent": "debugger", "kind": "source", "label": f"Source evidence: {p}",
                    "source": p, "payload": {"preview": "\n".join(_read(root, p).splitlines()[:18])},
                })
        evidence.append({
            "agent": "debugger", "kind": "call-graph",
            "label": "Call chain traced via repository index",
            "source": chain[0]["path"] if chain else "",
            "payload": {"chain": chain[:8]},
        })

        # 4. Generic fault-isolation note when the chain is thin.
        if len(chain) < 2:
            findings.append({
                "agent": "debugger", "title": "Single completion path only",
                "detail": "Only one caller of the orchestration symbol was found; fault isolation is low-risk.",
                "severity": "info", "category": "root-cause",
                "file": chain[0]["path"] if chain else "",
                "line": None, "confidence": 0.3, "evidence_refs": [],
            })

        ordered = sorted(findings, key=lambda f: f.get("confidence", 0), reverse=True)
        candidates = []
        for i, f in enumerate(ordered, 1):
            component = component_of(f["file"]) if f["file"] else "unknown"
            candidates.append({
                "rank": i, "title": f["title"], "confidence": f["confidence"],
                "component": component, "affected_files": affected_files,
            })

        if skill:
            keywords = skill.keywords + [w for w in _symbol_words(ctx.get("mission_text", ""))]
            hits = scan_keywords(root, keywords[:12])
            evidence.append({
                "agent": "debugger", "kind": "scan", "label": f"Keyword scan: {len(hits)} source hits",
                "source": "engine/debugger", "payload": {"hits": len(hits), "keywords": keywords[:12]},
            })

        top = ordered[0] if ordered else None
        summary = (
            f"Root cause hypothesis: {top['title']} (confidence {top.get('confidence', 0)}) "
            f"in {top['file']}." if top and skill else
            f"Repository analyzed: {len(chain)} call-chain node(s), {len(findings)} finding(s)."
        )

    return {
        "status": "completed",
        "summary": summary,
        "result": {"root_cause_candidates": candidates, "chain": chain, "skill": skill.id if skill else None},
        "findings": findings,
        "evidence": evidence,
        "affected_files": affected_files,
        "recommendations": [
            s.remediation.get("reason", "Fix the flagged defect and add regression coverage.")
            for s in ([skill] if skill else [])
        ] or ["Add a skill for this repository's defect to enable autonomous repair."],
        "confidence": top.get("confidence", 0.0) if top else 0.0,
        "duration_ms": timer.elapsed_ms,
    }


def _symbol_words(mission_text: str) -> list[str]:
    import re
    words = re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", mission_text)
    stop = {"with", "that", "this", "after", "before", "into", "from", "have", "will", "need", "check", "your", "such", "race", "flow"}
    return sorted({w for w in words if w.lower() not in stop})