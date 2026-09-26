"""Skill learning — FORGE records verified AI fixes and reuses them deterministically."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.intel.upload import extract_upload, register_repository
from app.skills import learn

from test_llm import SYNTHETIC_REPO, _zip


def _run_fix_mission(monkeypatch, tmp_path, mission_id: str, failures: int = 0):
    """Run the full pipeline with a fake LLM repair that fixes cart.py."""

    from app import config, store
    from app.orchestration import pipeline
    from tests.test_llm import _fake_repair, _fake_run_tester

    data = _zip(SYNTHETIC_REPO)
    root, name = extract_upload(data, "learnlab")
    register_repository(root, name)

    monkeypatch.setattr(config, "LLM_ENABLED", True)
    monkeypatch.setattr(pipeline.config, "LLM_ENABLED", True)
    monkeypatch.setattr(pipeline.repair_agent, "run_repair", _fake_repair("repair"))
    monkeypatch.setattr(pipeline.tester_agent, "run_tester", _fake_run_tester(failures))

    store.create_mission(mission_id, title="Fix cart", mission_text="cart explodes",
                         repository=name, seed=1)
    pipeline.run_mission(mission_id, "cart explodes on empty input", 1, name)
    return name


def test_buggy_lines_extracts_distinctive_removed_lines():
    diff = (
        "--- a/cart.py\n+++ b/cart.py\n"
        "@@ -1,2 +1,3 @@\n"
        "-def subtotal(line_items):\n"
        " def process_region(options): return 'who knows that'_responsibly\n"
        "+def subtotal(line_items):\n"
        "+    return 0\n"
    )
    lines = learn._buggy_lines(diff)
    assert "def subtotal(line_items):" in lines
    # context (space) lines are never treated as buggy
    assert "def process_region(options): return 'who knows that'_responsibly" not in lines


def test_learn_creates_skill_from_verified_ai_fix(monkeypatch, tmp_path):
    from app import store

    mission_id = "mission-learn-1"
    name = _run_fix_mission(monkeypatch, tmp_path, mission_id, failures=0)

    # The pipeline learns automatically; at least one learned playbook exists.
    learned = sorted(learn.SKILLS_DIR.glob("learned-*"))
    assert len(learned) == 1
    skill_dir = Path(learned[0])
    manifest_path = skill_dir / "manifest.json"
    assert manifest_path.exists()
    manifest = __import__("json").loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["detect"]["signals"][0]["path"] == "cart.py"
    assert manifest["remediation"]["patches"][0]["path"] == "cart.py"
    # learned skills carry critic-verifiable evidence: scope + correctness hints
    assert manifest["criteria"]["correctness_hints"]
    assert "root" in manifest["criteria"]["scope_prefixes"]
    # the patch holds the fixed file content
    patch_file = skill_dir / manifest["remediation"]["patches"][0]["template"]
    assert "return 0" in patch_file.read_text(encoding="utf-8")
    # registry can load the learned skill
    from app.skills.registry import load_all
    ids = [s.id for s in load_all()]
    assert manifest["id"] in ids
    # explicit re-learn is idempotent: nothing new creates
    assert learn.learn_from_mission(mission_id) == []
    audit = [a for a in store.get_audit(mission_id) if "Learned skill" in a.message]
    assert audit


def test_learn_dedupes_same_defect(monkeypatch, tmp_path):
    mission_id = "mission-learn-2"
    _run_fix_mission(monkeypatch, tmp_path, mission_id, failures=0)
    first = learn.learn_from_mission(mission_id)
    second = learn.learn_from_mission(mission_id)
    assert first == second
    assert learn.learned_skill_count() == 1


def test_learn_skips_non_ai_changes(tmp_path):
    from app import store

    mission_id = "mission-learn-3"
    store.create_mission(mission_id, title="x", mission_text="x", repository="nope", seed=1)
    store.add_code_change(mission_id, "cart.py", "M", 1, 0, "", "a skill patch fix")
    assert learn.learn_from_mission(mission_id) == []