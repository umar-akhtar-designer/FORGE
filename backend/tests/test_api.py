"""API round-trip tests via FastAPI TestClient (real mission execution)."""

import time

from fastapi.testclient import TestClient

from app.main import app

MISSION_TEXT = "Investigate a race condition in the checkout flow where a second confirm can fail or duplicate the order."


def _wait_completed(client: TestClient, mission_id: str, timeout: int = 90) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = client.get(f"/api/missions/{mission_id}").json()
        if detail["status"] in ("completed", "failed"):
            return detail
        time.sleep(1)
    raise TimeoutError(mission_id)


def test_launch_and_poll_mission_end_to_end():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"

        resp = client.post("/api/missions", json={"title": "Checkout race", "mission_text": MISSION_TEXT})
        assert resp.status_code == 200, resp.text
        mission_id = resp.json()["mission_id"]

        detail = _wait_completed(client, mission_id)
        assert detail["status"] == "completed"
        assert detail["outcome"] == "success"
        assert detail["gate_overall"] == "pass"
        assert len(detail["steps"]) == 10
        assert len(detail["agents"]) == 8


def test_report_contract_and_release_gate():
    with TestClient(app) as client:
        mission_id = client.post("/api/missions", json={"mission_text": MISSION_TEXT}).json()["mission_id"]
        _wait_completed(client, mission_id)

        rpt = client.get(f"/api/missions/{mission_id}/report")
        assert rpt.status_code == 200
        d = rpt.json()
        assert d["release_gate"]["overall"] == "pass"
        assert all(c["status"] == "pass" for c in d["release_gate"]["checks"])
        assert d["root_cause"] and d["root_cause"]["severity"] in ("high", "critical")
        assert len(d["evidence_graph"]["nodes"]) == 9
        # Every metric is tagged as measured or estimate.
        assert all(m["source"] in ("measured", "estimate") for m in d["metrics"])

        impact = client.get(f"/api/missions/{mission_id}/impact").json()
        assert "estimate" in impact["baseline_label"].lower()

        gates = client.get(f"/api/missions/{mission_id}/release-gate").json()
        assert gates["overall"] == "pass"

        activity = client.get(f"/api/missions/{mission_id}/activity").json()
        assert len(activity["events"]) > 5

        assert client.get(f"/api/missions/{mission_id}/report").json()["mission"]["id"] == mission_id


def test_repositories_and_sources_endpoints():
    with TestClient(app) as client:
        _wait_completed(client, client.post("/api/missions", json={"mission_text": MISSION_TEXT}).json()["mission_id"])
        repos = client.get("/api/repositories").json()
        assert any(r["name"] == "forgemart" for r in repos)
        assert client.get("/api/sources/registry").json() and client.get("/api/sources/registry").status_code == 200