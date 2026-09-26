"""Evidence graph — the visual signature of a mission.

Nodes map to the blueprint: USER MISSION → REPOSITORY EVIDENCE → ROOT CAUSE →
FIX PLAN → CODE CHANGES → {TESTS, SECURITY} → CRITIC REVIEW → RELEASE GATE.
Node status is derived from real mission artifacts (never guessed).
"""

from __future__ import annotations

from .. import store


def build(missions: list, agents: list, findings: list, evidence: list, changes: list, reviews: list, gates: list, mission) -> dict:
    agent_map = {a.agent: a for a in agents}
    status = mission.status

    def node(nid: str, label: str, kind: str, st: str, count: int = 0, detail: str = "") -> dict:
        return {"id": nid, "label": label, "kind": kind, "status": st, "count": count, "detail": detail}

    base = "completed" if status == "completed" else ("running" if status == "running" else "pending")

    nodes = [
        node("mission", "USER MISSION", "mission", base),
        node("evidence", "REPOSITORY EVIDENCE", "evidence", base, count=len(evidence)),
        node("root-cause", "ROOT CAUSE", "analysis", base if (findings and any(f.severity in ("high", "critical") for f in findings)) else "pending", count=len([f for f in findings if f.severity in ("high", "critical")])),
        node("plan", "FIX PLAN", "plan", base if any(a.agent == "debugger" and a.status == "completed" for a in agents) else "pending"),
        node("changes", "CODE CHANGES", "change", base if changes else "pending", count=len(changes)),
        node("tests", "TESTS", "validate", base if (agent_map.get("tester") and agent_map["tester"].status == "completed") else "pending"),
        node("security", "SECURITY", "validate", base if (agent_map.get("security") and agent_map["security"].status == "completed") else "pending"),
        node("critic", "CRITIC REVIEW", "review", reviews[0].verdict if reviews else "pending"),
        node("release", "RELEASE GATE", "gate", gates[0].overall if gates else "blocked"),
    ]

    edges = [
        ("mission", "evidence", "flow"),
        ("evidence", "root-cause", "flow"),
        ("root-cause", "plan", "flow"),
        ("plan", "changes", "flow"),
        ("changes", "tests", "flow"),
        ("changes", "security", "flow"),
        ("tests", "critic", "flow"),
        ("security", "critic", "flow"),
        ("critic", "release", "flow"),
    ]
    return {"nodes": nodes, "edges": [{"source": s, "target": t, "kind": k} for s, t, k in edges]}