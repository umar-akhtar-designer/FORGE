"""The evidence graph must speak the frontend's status vocabulary."""

from types import SimpleNamespace

from app.orchestration import evidence as evidence_graph


def test_gate_status_normalization():
    assert evidence_graph.gate_status("ready") == "pass"
    assert evidence_graph.gate_status("blocked") == "fail"
    assert evidence_graph.gate_status("in_progress") == "running"
    assert evidence_graph.gate_status("pending") == "pending"


def test_release_gate_node_lights_pass_when_green():
    mission = SimpleNamespace(status="completed")
    agents = [
        SimpleNamespace(agent="debugger", status="completed"),
        SimpleNamespace(agent="tester", status="completed"),
        SimpleNamespace(agent="security", status="completed"),
    ]
    findings = [SimpleNamespace(severity="high")]
    reviews = [SimpleNamespace(verdict="pass")]
    gates = [SimpleNamespace(overall="ready")]

    graph = evidence_graph.build(
        missions=[mission], agents=agents, findings=findings, evidence=["e"],
        changes=[object()], reviews=reviews, gates=gates, mission=mission,
    )
    nodes = {n["id"]: n["status"] for n in graph["nodes"]}
    assert nodes["release"] == "pass"
    assert nodes["critic"] == "pass"
    assert nodes["tests"] == "completed"
    assert nodes["security"] == "completed"


def test_release_gate_node_red_when_blocked():
    mission = SimpleNamespace(status="completed")
    reviews = [SimpleNamespace(verdict="changes_requested")]
    gates = [SimpleNamespace(overall="blocked")]

    graph = evidence_graph.build(
        missions=[mission], agents=[], findings=[],
        evidence=[], changes=[object()], reviews=reviews, gates=gates, mission=mission,
    )
    nodes = {n["id"]: n["status"] for n in graph["nodes"]}
    assert nodes["release"] == "fail"
    assert nodes["critic"] == "changes_requested"