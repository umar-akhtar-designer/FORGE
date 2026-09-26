"""Pipeline contract tests — one mission drives the full workflow end to end."""

import uuid

import pytest

from app import store
from app.orchestration import pipeline, report

MISSION_TEXT = "Investigate a race condition in the checkout flow where a second confirm can fail or duplicate the order."


def _run(text: str) -> str:
    mid = f"pytest-{uuid.uuid4().hex[:10]}"
    store.create_mission(mid, "Checkout race", text, "forgemart", 0)
    pipeline.run_mission(mid, text, 0, "forgemart")
    return mid


def test_mission_succeeds_and_ready_for_release():
    mid = _run(MISSION_TEXT)
    m = store.get_mission(mid)
    assert m.status == "completed"
    assert m.outcome == "success"
    gates = store.get_gates(mid)
    assert gates and gates[0].overall == "ready"
    assert all(g.status == "pass" for g in gates)


def test_release_gate_cheatsheet_exists():
    """The seven release gates are always evaluated."""
    mid = _run(MISSION_TEXT)
    gates = store.get_gates(mid)
    names = {g.name for g in gates}
    assert names == {"build", "unit_tests", "regression", "security", "code_review", "architecture", "scope"}


def test_root_cause_identifies_the_defect():
    mid = _run(MISSION_TEXT)
    r = report.build(mid)
    assert r["root_cause"] is not None
    assert r["root_cause"]["category"] == "root-cause"
    assert "idempotent" in r["root_cause"]["title"].lower()


def test_regression_test_generated_and_green_after_fix():
    mid = _run(MISSION_TEXT)
    r = report.build(mid)
    inv = [t for t in r["tests"] if t["phase"] == "investigate" and "checkout.race" in t["path"]]
    val = [t for t in r["tests"] if t["phase"] == "validate" and "checkout.race" in t["path"]]
    # Pre-fix evidence: the generated regression reproduces the defect on the buggy workspace.
    assert len(inv) == 2 and all(t["status"] == "failed" for t in inv)
    # Post-fix evidence: the same regression is green on the changed workspace.
    assert len(val) == 2 and all(t["status"] == "passed" for t in val)
    assert all("tests/regression/checkout.race.test.ts" in t["path"] for t in inv + val)


def test_code_changes_apply_only_to_payments_and_database():
    mid = _run(MISSION_TEXT)
    r = report.build(mid)
    paths = {c["path"] for c in r["code_changes"]}
    assert paths == {"packages/payments/src/checkout.ts", "packages/database/src/orders.ts"}
    # The diff must be real and reviewable.
    combined = r["code_changes"][0]["diff"] + "".join(c["diff"] for c in r["code_changes"])
    assert combined.startswith("---") or "a/packages" in combined


def test_security_has_no_critical():
    mid = _run(MISSION_TEXT)
    r = report.build(mid)
    assert r["security_scan"]["critical"] == 0
    assert any(sf["severity"] == "high" for sf in r["security"])  # webhook-unverified is expected by design


def test_critic_approves_after_fix():
    mid = _run(MISSION_TEXT)
    reviews = store.get_reviews(mid)
    assert reviews and reviews[0].verdict == "pass"


def test_evidence_graph_wires_every_stage():
    mid = _run(MISSION_TEXT)
    r = report.build(mid)
    ids = {n["id"] for n in r["evidence_graph"]["nodes"]}
    assert {"mission", "evidence", "root-cause", "plan", "changes", "tests", "security", "critic", "release"} <= ids


def test_replay_is_deterministic():
    mid_a = _run(MISSION_TEXT)
    mid_b = _run(MISSION_TEXT)
    ta = {f["title"] for f in report.build(mid_a)["findings"]}
    tb = {f["title"] for f in report.build(mid_b)["findings"]}
    assert ta == tb
    ga = [(g.name, g.status) for g in store.get_gates(mid_a)]
    gb = [(g.name, g.status) for g in store.get_gates(mid_b)]
    assert ga == gb