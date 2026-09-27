"""GitHub integration — diff reconstruction, repo connect, PR endpoint guards."""

from __future__ import annotations

import difflib
import io
import zipfile


def _udiff(before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile="a/x.py", tofile="b/x.py"))


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_apply_unified_diff_reconstructs_content():
    from app.intel.diff import apply_unified_diff as _apply_unified_diff

    before = "def add(a, b):\n    return a + b\n"
    after = "def add(a, b):\n    if b is None:\n        b = 0\n    return a + b\n"
    diff = _udiff(before, after)
    assert _apply_unified_diff(before, diff) == after


def test_apply_unified_diff_new_file():
    from app.intel.diff import apply_unified_diff as _apply_unified_diff

    before = ""
    after = "print('hello')\n"
    diff = _udiff(before, after)
    assert _apply_unified_diff(before, diff) == after


def test_apply_unified_diff_no_newline_at_eof():
    from app.intel.diff import apply_unified_diff as _apply_unified_diff

    before = "x = 1"
    after = "x = 2"
    diff = _udiff(before, after)
    assert _apply_unified_diff(before, diff) == after


def test_pr_endpoint_guards_without_config(monkeypatch):
    from app import config
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(config, "GITHUB_TOKEN", "")
    monkeypatch.setattr(config, "GITHUB_REPO", "")
    client = TestClient(app)
    res = client.post("/api/missions/whatever/pr")
    assert res.status_code == 400
    assert "not enabled" in res.json()["detail"]

    res = client.get("/api/github/status")
    assert res.status_code == 200
    assert res.json() == {"enabled": False, "repository": None}


def test_parse_repo_url_variants():
    from app.intel.github_api import parse_repo_url

    assert parse_repo_url("https://github.com/octo/repo") == ("octo", "repo", None)
    assert parse_repo_url("https://github.com/octo/repo/tree/dev") == ("octo", "repo", "dev")
    assert parse_repo_url("https://github.com/octo/repo.git") == ("octo", "repo", None)
    assert parse_repo_url("git@github.com:octo/repo.git") == ("octo", "repo", None)
    assert parse_repo_url("octo/repo") == ("octo", "repo", None)


def test_parse_repo_url_rejects_garbage():
    from app.intel.github_api import parse_repo_url

    for bad in ("not a url", "https://example.com/x", "repo-only"):
        try:
            parse_repo_url(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_connect_repository_happy_path(monkeypatch, tmp_path):
    from app import store
    from app.intel import github_api as gapi

    repo_zip = _zip({"src/main.py": b"print('hi')\n"})

    class _Resp:
        content = repo_zip
        status_code = 200
        text = ""
        def json(self):
            return {}

    monkeypatch.setattr(gapi.httpx, "get", lambda *a, **k: _Resp())
    idx = gapi.connect_repository("acme/widgets")
    assert idx["source"]["owner"] == "acme"
    assert idx["source"]["repo"] == "widgets"
    assert idx["stats"]["files"] == 1
    # registered so missions can target it
    assert any(i.name == idx["name"] for i in store.list_repository_indexes())


def test_connect_repository_bad_url_400(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    res = client.post("/api/repositories/connect", json={"url": "not a url"})
    assert res.status_code == 400


def test_connect_repository_codeload_down_surfaces_error(monkeypatch):
    import time

    from app.intel import github_api as gapi
    from app.main import app
    from fastapi.testclient import TestClient

    class _Bad:
        status_code = 404
        text = "Not Found"
        def json(self):
            return {}

    repo = "acme/codeload-down"
    monkeypatch.setattr(gapi.httpx, "get", lambda *a, **k: _Bad())
    client = TestClient(app)
    res = client.post("/api/repositories/connect", json={"url": repo})
    assert res.status_code == 202

    for _ in range(50):
        st = client.get(f"/api/repositories/connect/status?url={repo}").json()
        if st["status"] == "error":
            break
        time.sleep(0.02)
    assert st["status"] == "error"
    assert st["message"]