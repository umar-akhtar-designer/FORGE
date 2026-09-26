"""Skill registry tests — the engine must stay repository-agnostic."""

import tempfile
from pathlib import Path

from app import config
from app.skills import get, load_all, matched, run_observations


def test_registry_loads_checkout_race_skill():
    skills = load_all()
    assert any(s.id == "checkout-race" for s in skills)
    skill = get("checkout-race")
    assert skill is not None
    assert skill.remediation["patches"] and skill.regression["dest"].endswith(".race.test.ts")


def test_skill_matches_forgemart_workspace():
    skill = get("checkout-race")
    hits = matched(config.FORGEMART_DIR)
    assert any(s.id == "checkout-race" for s, _ in hits)


def test_skill_does_not_match_bare_directory():
    skill = get("checkout-race")
    with tempfile.TemporaryDirectory() as tmp:
        assert matched(Path(tmp)) == []


def test_observations_produce_real_line_evidence():
    skill = get("checkout-race")
    findings = run_observations(skill, config.FORGEMART_DIR)
    titles = {f["title"] for f in findings}
    assert "Order creation is not idempotent for a session" in titles
    assert "Payment hold released before idempotency is guaranteed" in titles
    for f in findings:
        assert f["file"] and f["line"] and f["confidence"] > 0.5
        assert any("@" in ref and ref.split("@")[1].isdigit() for ref in f["evidence_refs"])


def test_probe_does_not_fire_when_guard_present(tmp_path: Path):
    """A repo whose create() is already idempotent must not be flagged."""
    skill = get("checkout-race")
    (tmp_path / "packages" / "database" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "payments" / "src").mkdir(parents=True)
    (tmp_path / "apps" / "api" / "src" / "webhooks").mkdir(parents=True)
    (tmp_path / "apps" / "api" / "src" / "routes").mkdir(parents=True)
    (tmp_path / "packages" / "payments" / "src" / "checkout.ts").write_text(
        "export async function completeCheckout() {\n  orders.create();\n  lock.release();\n}\n"
    )
    (tmp_path / "apps" / "api" / "src" / "webhooks" / "payment.ts").write_text(
        "if (evt.type === 'checkout.session.completed') {}\n"
    )
    # create() guards on existing order -> probe must stay silent
    (tmp_path / "packages" / "database" / "src" / "orders.ts").write_text(
        "async create(session) {\n  const existing = this.findBySession(session.id); if (existing) return existing;\n}\n"
    )
    findings = run_observations(skill, tmp_path)
    assert "Order creation is not idempotent for a session" not in {f["title"] for f in findings}