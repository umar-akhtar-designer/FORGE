"""API security — token auth and rate limiting (env-gated, fail closed)."""

from __future__ import annotations

import io
import zipfile


def _token():
    return {"Authorization": f"Bearer {_TOKEN_VALUE}"}


_TOKEN_VALUE = "forge-test-secret"


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_write_routes_require_token_when_configured(monkeypatch):
    from app import config
    from app.intel import github_api as gapi
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(config, "API_TOKEN", _TOKEN_VALUE)
    client = TestClient(app)

    # without token -> 401
    res = client.post("/api/repositories/connect", json={"url": "acme/widgets"})
    assert res.status_code == 401

    # with token -> happy path (codeload mocked so no network)
    class _Resp:
        content = _zip({"src/main.py": b"print('hi')\n"})
        status_code = 200
        text = ""
        def json(self):
            return {}

    monkeypatch.setattr(gapi.httpx, "get", lambda *a, **k: _Resp())
    res = client.post("/api/repositories/connect", json={"url": "acme/widgets"}, headers=_token())
    assert res.status_code == 200


def test_write_routes_open_when_token_disabled(monkeypatch):
    from app import config
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(config, "API_TOKEN", "")
    client = TestClient(app)
    res = client.post("/api/repositories/connect", json={"url": "acme/widgets"})
    assert res.status_code != 401


def test_read_routes_stay_open_with_token_configured(monkeypatch):
    from app import config
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(config, "API_TOKEN", _TOKEN_VALUE)
    client = TestClient(app)
    res = client.get("/api/health")
    assert res.status_code == 200


def test_rate_limit_429_after_limit(monkeypatch):
    from app import config
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(config, "API_RATE_LIMIT", 3)
    client = TestClient(app)
    codes = [client.get("/api/health").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]