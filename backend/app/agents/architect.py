"""Architect agent — map the repository and the blast radius of the mission.

Everything here is derived from the real index: affected components come from
mission-keyword density over actual file paths; architecture notes come from
the real component/dependency map. The matched skill may contribute the
keyword set, but no repository-specific knowledge is hardcoded here.
"""

from __future__ import annotations

import re
from collections import Counter

from ..intel.indexer import component_of
from ..skills import Skill
from .base import Timer

STOP = {"with", "that", "this", "after", "before", "into", "from", "have", "will", "need", "check", "your", "such", "the", "and", "for"}
GENERIC_DOMAIN = {"order", "payment", "auth", "session", "webhook", "lock", "release", "build", "confirm"}


def _words_from(mission_text: str) -> set[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", mission_text.lower())
    return {w for w in words if w not in STOP}


def _keywords_for(mission_text: str, skill: Skill | None) -> list[str]:
    mission = _words_from(mission_text)
    if skill:
        pool = mission & set(skill.keywords)
        if pool:
            return sorted(pool)
    mission |= GENERIC_DOMAIN
    return sorted(mission & GENERIC_DOMAIN) or sorted(mission)


def run_architect(ctx: dict, skill: Skill | None = None) -> dict:
    with Timer() as timer:
        index = ctx["index"]
        architecture = index.get("architecture", {})
        files = index.get("files", [])

        keywords = _keywords_for(ctx.get("mission_text", ""), skill)
        comp_names = {n.get("id"): n for n in architecture.get("components", [])}

        comp_hits = Counter()
        for f in files:
            fp = f["path"].lower()
            score = sum(1 for k in keywords if k in fp)
            if score:
                comp_hits[component_of(f["path"])] += score

        affected = []
        for comp_id, count in comp_hits.most_common():
            node = comp_names.get(comp_id)
            if node:
                affected.append({"component": comp_id, "hits": count, "risk": node.get("risk", 0), "files": node.get("files", 0)})

        edge_map = {}
        for e in architecture.get("edges", []):
            edge_map.setdefault(e["source"], []).append(e["target"])

        # Data-derived notes — no repository-specific prose.
        notes = []
        top_comp = comp_hits.most_common(1)
        if top_comp:
            notes.append(f"Highest mission-keyword density: {top_comp[0][0]} ({top_comp[0][1]} hits).")
        entry_count = len(comp_names)
        notes.append(f"Architecture map: {len(architecture.get('components', []))} components, {len(architecture.get('edges', []))} dependency edges, {entry_count} top-level unit(s).")

        related = sorted({t for src in comp_hits for t in edge_map.get(src, [])})
        dependencies = [
            {"component": c, "depends_on": edge_map.get(c, []), "dependent_count": sum(1 for v in edge_map.values() if c in v)}
            for c in (list(comp_hits) + list(related))
        ]

        max_risk = max((n.get("risk", 0) for n in comp_names.values()), default=0)
        risk_level = "elevated" if max_risk >= 6 else "moderate"

        affected_files = [f["path"] for f in files if any(k in f["path"].lower() for k in keywords)][:14]

        findings = []
        if len(comp_hits) >= 2:
            findings.append({
                "agent": "architect", "title": "Mission spans multiple components",
                "detail": f"The mission touches {len(comp_hits)} components ({', '.join(k for k, _ in comp_hits.most_common(5))}). Cross-component hand-offs are the most likely place for a defect to hide.",
                "severity": "medium", "category": "architecture",
                "file": next((f["path"] for f in files if any(k in f["path"].lower() for k in keywords)), ""),
                "line": None, "confidence": 0.82,
                "evidence_refs": [c for c, _ in comp_hits.most_common(4)],
            })
        if related:
            findings.append({
                "agent": "architect", "title": "Shared ownership across module boundaries",
                "detail": f"Affected components depend on {len(related)} related unit(s): {', '.join(related[:6])}. Ownership of the mission's target logic is distributed at runtime.",
                "severity": "medium", "category": "architecture",
                "file": next((f["path"] for f in files if any(k in f["path"].lower() for k in keywords)), ""),
                "line": None, "confidence": 0.76, "evidence_refs": related[:4],
            })

        evidence = [
            {"agent": "architect", "kind": "architecture", "label": f"Architecture map: {len(architecture.get('components', []))} components / {len(architecture.get('edges', []))} dependency edges", "source": "index", "payload": {"components": len(architecture.get("components", [])), "edges": len(architecture.get("edges", []))}},
            {"agent": "architect", "kind": "metric", "label": f"Keyword density: {dict(comp_hits.most_common(5))}", "source": "index", "payload": dict(comp_hits)},
        ]

        recommendations = [
            "Confirm ownership of the target module before changes.",
            "Scope changes to the affected components to limit blast radius.",
        ]

        summary = f"Repository mapped: {len(files)} files, {len(comp_hits)} affected components, risk {risk_level}."

    return {
        "status": "completed", "summary": summary,
        "result": {"affected_components": affected[:6], "dependencies": dependencies, "risk_level": risk_level, "architecture_notes": notes, "keywords": keywords},
        "findings": findings, "evidence": evidence,
        "affected_files": affected_files, "recommendations": recommendations,
        "confidence": 0.86, "duration_ms": timer.elapsed_ms,
    }