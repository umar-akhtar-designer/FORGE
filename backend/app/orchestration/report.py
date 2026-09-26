"""Mission report assembly — converts ORM rows into the MissionReport contract.

All values come straight from the evidence store; nothing is estimated except
the clearly-labeled manual-workflow baseline.
"""

from __future__ import annotations

import re

from .. import store
from ..orm import Mission
from ..intel.indexer import architecture_map, dependencies_manifest  # noqa: F401  (kept for symmetry)
from ..skills import load_all
from . import evidence as evidence_graph


def _mission_summary(m: Mission) -> dict:
    steps = store.get_steps(m.id)
    total = len(steps)
    done = sum(1 for s in steps if s.status in ("completed", "skipped", "failed"))
    progress = round(done / total, 2) if total else 0.0
    return {
        "id": m.id, "title": m.title, "repository": m.repository,
        "status": m.status, "outcome": m.outcome, "progress": progress,
        "summary": m.summary,
        "created_at": m.created_at, "started_at": m.started_at, "completed_at": m.completed_at,
        "duration_ms": m.duration_ms, "error": m.error,
    }


def build(mission_id: str) -> dict:
    m = store.get_mission(mission_id)
    if m is None:
        raise KeyError(mission_id)

    agents = store.get_agents(mission_id)
    findings = store.get_findings(mission_id)
    evidence = store.get_evidence(mission_id)
    changes = store.get_code_changes(mission_id)
    tests = store.get_tests(mission_id)
    security = store.get_security(mission_id)
    reviews = store.get_reviews(mission_id)
    gates = store.get_gates(mission_id)
    metrics = store.get_metrics(mission_id)
    activity = store.get_audit(mission_id)
    index = store.get_repository_index(m.repository)

    repo_out = {
        "name": index.name if index else m.repository,
        "path": index.path if index else "",
        "stats": index.stats if index else {},
        "files": index.files if index else [],
        "tests": index.tests if index else [],
        "architecture": index.architecture if index else {"components": [], "edges": []},
        "dependencies": index.dependencies if index else [],
    }

    sec_findings = security if security else []
    sec_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for sf in sec_findings:
        key = sf.severity if sf.severity in sec_counts else "info"
        sec_counts[key] += 1

    root_cause = next((f for f in findings if f.category == "root-cause" and f.severity in ("high", "critical")), None) or (findings[0] if findings and findings[0].category == "root-cause" else None)
    planning = [f for f in findings if f.category == "architecture"]

    gate_out = {"checks": [], "overall": "in_progress"}
    if gates:
        gate_out = {
            "overall": gates[0].overall if gates else "in_progress",
            "checks": [{"name": g.name, "status": g.status, "detail": g.detail, "order_index": g.order_index, "checked_at": g.checked_at} for g in gates],
        }

    graph = evidence_graph.build(
        missions=[m], agents=agents, findings=findings, evidence=evidence,
        changes=changes, reviews=reviews, gates=gates, mission=m)

    baseline_min = 0
    for met in metrics:
        if met.key == "manual_baseline_min":
            baseline_min = int(met.value)

    matched_ids = set()
    for a in activity:
        if a.category == "matched":
            match = re.search(r"\(([a-zA-Z0-9._-]+)\)\s*$", a.message)
            if match:
                matched_ids.add(match.group(1))
    skills = [{"matched": s.id in matched_ids, **s.public()} for s in load_all()]

    msum = _mission_summary(m)
    return {
        "mission": msum,
        "summary": m.summary or "Mission completed.",
        "repository": repo_out,
        "root_cause": {
            "id": root_cause.id, "agent": root_cause.agent, "title": root_cause.title,
            "detail": root_cause.detail, "severity": root_cause.severity, "category": root_cause.category,
            "file": root_cause.file, "line": root_cause.line, "confidence": root_cause.confidence,
            "evidence_refs": root_cause.evidence_refs,
        } if root_cause else None,
        "planning": [{"id": f.id, "agent": f.agent, "title": f.title, "detail": f.detail, "severity": f.severity, "category": f.category, "file": f.file, "line": f.line, "confidence": f.confidence, "evidence_refs": f.evidence_refs} for f in planning],
        "findings": [{"id": f.id, "agent": f.agent, "title": f.title, "detail": f.detail, "severity": f.severity, "category": f.category, "file": f.file, "line": f.line, "confidence": f.confidence, "evidence_refs": f.evidence_refs} for f in findings],
        "evidence": [{"id": e.id, "agent": e.agent, "kind": e.kind, "label": e.label, "source": e.source, "payload": e.payload} for e in evidence],
        "code_changes": [{"id": c.id, "path": c.path, "status": c.status, "added": c.added, "removed": c.removed, "diff": c.diff, "reason": c.reason} for c in changes],
        "tests": [{"id": t.id, "suite": t.suite, "phase": t.phase, "path": t.path, "name": t.name, "status": t.status, "duration_ms": t.duration_ms, "detail": t.detail} for t in tests],
        "security": [{"id": sf.id, "rule": sf.rule, "severity": sf.severity, "title": sf.title, "path": sf.path, "line": sf.line, "description": sf.description, "remediation": sf.remediation} for sf in sec_findings],
        "security_scan": sec_counts,
        "reviews": [{"id": r.id, "reviewer": r.reviewer, "verdict": r.verdict, "score": r.score, "summary": r.summary, "issues": r.issues_json, "reviewed_files": r.reviewed_files} for r in reviews],
        "release_gate": gate_out,
        "metrics": [{"key": mt.key, "label": mt.label, "value": mt.value, "unit": mt.unit, "source": mt.source, "order_index": mt.order_index} for mt in metrics],
        "activity": [{"agent": a.agent, "category": a.category, "message": a.message, "at": a.at} for a in activity],
        "evidence_graph": graph,
        "skills": skills,
        "workflow_time_ms": m.duration_ms,
        "baseline_minutes": baseline_min,
    }