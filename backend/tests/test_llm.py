"""Generative repair — LLM client parsing, proposal application, pipeline honesty."""

from __future__ import annotations

import io
import zipfile

from app.intel.upload import extract_upload, register_repository

SYNTHETIC_REPO = {
    "cart.py": (
        "def subtotal(line_items):\n"
        "    return sum(item['price'] * item['qty'] for item in line_items)\n"
    ),
    "shop.py": (
        "from cart import subtotal\n\n"
        "def total(items):\n"
        "    return round(subtotal(items), 2)\n"
    ),
}


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_chat_json_strips_markdown_fences(monkeypatch):
    from app.llm import chat_json

    monkeypatch.setattr(
        "app.llm.chat",
        lambda *a, **k: '```json\n{"files": [{"path": "a.py", "new_content": "x"}]}\n```',
    )
    out = chat_json([{"role": "user", "content": "hi"}])
    assert out["files"][0]["path"] == "a.py"


def test_bad_llm_output_raises(monkeypatch):
    from app.llm import chat_json, LLMError

    monkeypatch.setattr("app.llm.chat", lambda *a, **k: "not json at all")
    try:
        chat_json([{"role": "user", "content": "hi"}])
    except LLMError:
        return
    raise AssertionError("expected LLMError for non-JSON output")


def _ctx(tmp_path):
    root = tmp_path / "root"
    pristine = tmp_path / "pristine"
    root.mkdir(); pristine.mkdir()
    for name, content in SYNTHETIC_REPO.items():
        (pristine / name).write_text(content, encoding="utf-8")
        (root / name).write_text(content, encoding="utf-8")
    return {
        "root": root, "pristine": pristine, "mission_text": "cart explodes on empty input",
        "index": {}, "skills": [], "skill": None,
    }


def test_repair_applies_proposal_to_workspace_only(monkeypatch, tmp_path):
    from app.agents import repair

    ctx = _ctx(tmp_path)
    monkeypatch.setattr(
        repair, "chat_json",
        lambda *a, **k: {"files": [{"path": "cart.py", "new_content": "def subtotal(x):\n    return 0\n"}]},
    )
    debugger = {"result": {"root_cause_candidates": [{"rank": 1, "title": "no empty guard", "confidence": 0.9, "component": "cart"}], "chain": []}, "affected_files": ["cart.py"]}
    tester = {"result": {"tests": [{"path": "cart.py", "name": "subtotal empty", "status": "failed"}]}}
    out = repair.run_repair(ctx, debugger, tester)

    assert out["result"]["files"] == ["cart.py"]
    assert (ctx["root"] / "cart.py").read_text(encoding="utf-8").startswith("def subtotal(x)")
    assert (ctx["pristine"] / "cart.py").read_text(encoding="utf-8").startswith("def subtotal(line_items)")
    assert out["findings"] and out["findings"][0]["severity"] == "info"


def test_repair_reports_unavailable_llm(monkeypatch, tmp_path):
    from app.agents import repair
    from app.llm import LLMError

    ctx = _ctx(tmp_path)
    monkeypatch.setattr(repair, "chat_json", lambda *a, **k: (_ for _ in ()).throw(LLMError("boom")))
    debugger = {"result": {"root_cause_candidates": []}, "affected_files": ["cart.py"]}
    tester = {"result": {"tests": []}}
    out = repair.run_repair(ctx, debugger, tester)

    assert out["result"]["files"] == []
    assert "AI repair unavailable" in out["summary"]
    assert (ctx["root"] / "cart.py").read_text(encoding="utf-8").startswith("def subtotal(line_items)")


def test_repair_ignores_unknown_paths(monkeypatch, tmp_path):
    from app.agents import repair

    ctx = _ctx(tmp_path)
    monkeypatch.setattr(
        repair, "chat_json",
        lambda *a, **k: {"files": [{"path": "pwn.py", "new_content": "evil"}, {"path": "cart.py", "new_content": "ok\n"}]},
    )
    debugger = {"result": {"root_cause_candidates": []}, "affected_files": ["cart.py"]}
    tester = {"result": {"tests": []}}
    out = repair.run_repair(ctx, debugger, tester)
    assert out["result"]["files"] == ["cart.py"]
    assert not (ctx["root"] / "pwn.py").exists()


def _fake_run_tester(failures: int):
    def _run(ctx, skill=None):
        if ctx.get("phase") == "validate":
            return {
                "status": "completed", "summary": "fake validate",
                "result": {"phase": "validate", "tests": [],
                           "full": {"total": 3, "failed": failures, "files": 1, "ran": True},
                           "typecheck": {"exit_code": None, "ran": False}},
                "findings": [], "evidence": [], "affected_files": [],
                "recommendations": [], "confidence": 0.9, "duration_ms": 1,
            }
        return {
            "status": "completed", "summary": "fake investigate",
            "result": {"phase": "investigate", "runner": None, "tests": [], "generated": "",
                       "unit": {"total": 0, "failed": 0, "files": 0, "ran": False},
                       "regression": {"total": 0, "failed": 0}},
            "findings": [], "evidence": [], "affected_files": [],
            "recommendations": [], "confidence": 0.9, "duration_ms": 1,
        }
    return _run


def _fake_repair(failures_expected_note: str):
    def _run(ctx, debugger_payload, tester_payload):
        root = ctx["root"]
        (root / "cart.py").write_text("def subtotal(line_items):\n    return 0\n", encoding="utf-8")
        return {
            "status": "completed", "summary": "AI repair proposed cart.py",
            "result": {"proposed": [{"path": "cart.py", "content": "def subtotal(line_items):\n    return 0\n"}], "files": ["cart.py"]},
            "findings": [{"agent": "repair", "title": "proposed", "detail": "x", "severity": "info", "category": "implementation",
                          "file": "cart.py", "line": None, "confidence": 0.5, "evidence_refs": ["llm-call"]}],
            "evidence": [], "affected_files": ["cart.py"],
            "recommendations": [], "confidence": 0.5, "duration_ms": 1,
        }
    return _run


def _run_mission_with_repair(monkeypatch, tmp_path, failures: int):
    from app import store, config
    from app.orchestration import pipeline

    data = _zip(SYNTHETIC_REPO)
    root, name = extract_upload(data, "llmlab")
    register_repository(root, name)

    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(pipeline.config, "LLM_ENABLED", True)
    monkeypatch.setattr(pipeline.repair_agent, "run_repair", _fake_repair("repair"))
    monkeypatch.setattr(pipeline.tester_agent, "run_tester", _fake_run_tester(failures))

    mission_id = "mission-llm-0001"
    store.create_mission(mission_id, title="Fix cart", mission_text="cart explodes",
                         repository=name, seed=1)
    pipeline.run_mission(mission_id, "cart explodes on empty input", 1, name)
    return store, mission_id


def test_repair_commits_only_when_validation_passes(monkeypatch, tmp_path):
    store, mission_id = _run_mission_with_repair(monkeypatch, tmp_path, failures=0)
    changes = store.get_code_changes(mission_id)
    assert len(changes) == 1
    assert changes[0].path == "cart.py"
    assert "AI repair" in changes[0].reason
    mission = store.get_mission(mission_id)
    assert mission.outcome in ("success", "partial")


def test_repair_reverted_when_validation_fails(monkeypatch, tmp_path):
    store, mission_id = _run_mission_with_repair(monkeypatch, tmp_path, failures=1)
    assert store.get_code_changes(mission_id) == []
    rows = [a for a in store.get_audit(mission_id) if a.message and "AI repair was not verified" in a.message]
    assert rows
    mission = store.get_mission(mission_id)
    assert mission.outcome == "partial"