"""Bring-Your-Own-Software: safe uploads and the honest no-skill pipeline."""

from __future__ import annotations

import io
import zipfile

from app.intel.upload import extract_upload, register_repository


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


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
    "README.md": "A tiny store front that FORGE can inspect without running anything.\n",
}


def test_upload_rejects_path_traversal_and_absolute_paths():
    evil = _zip({**SYNTHETIC_REPO, "../escape.txt": b"pwn", "/tmp/abs.txt": b"pwn"})
    root, name = extract_upload(evil, "cart2")
    assert name == "cart2"
    files = sorted(p.name for p in root.rglob("*"))
    assert "cart.py" in files
    assert "shop.py" in files
    assert not any("escape" in p or "abs" in p for p in files)


def test_upload_skips_darwin_artifacts():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.py", "x = 1\n")
        zf.writestr("__MACOSX/app.py", "junk")
        zf.writestr(".DS_Store", "junk")
    root, _ = extract_upload(buf.getvalue())
    names = [p.name for p in root.rglob("*")]
    assert "__MACOSX" not in [p.parent.name for p in root.rglob("*")]
    assert ".DS_Store" not in names
    assert "app.py" in names


def test_upload_unwraps_single_top_level_folder():
    data = _zip({f"storefront/{k}": v for k, v in SYNTHETIC_REPO.items()})
    root, name = extract_upload(data, "wrapped")
    assert root.name == "storefront"
    assert (root / "cart.py").exists()


def test_upload_rejects_oversized_entry_count():
    data = _zip({f"f{i}.txt": b"x" * 10 for i in range(config_safe_max_entries() + 1)})
    try:
        extract_upload(data, "big")
    except ValueError as exc:
        assert "too many entries" in str(exc)
    else:
        raise AssertionError("expected ValueError for oversized archive")


def config_safe_max_entries() -> int:
    from app import config

    return config.MAX_ZIP_ENTRIES


def test_register_repository_indexes_upload(tmp_path):
    from app import store
    from app.intel.indexer import index_directory

    data = _zip(SYNTHETIC_REPO)
    root, name = extract_upload(data, "storefront")
    idx = register_repository(root, name)
    assert idx["name"] == "storefront"
    assert idx["stats"]["files"] >= 3
    assert store.get_repository_index("storefront") is not None
    files = index_directory(root)["files"]
    assert any(f["path"].endswith("cart.py") for f in files)


def test_upload_repo_mission_completes_honestly_without_fix():
    from app import store
    from app.orchestration import pipeline

    data = _zip(SYNTHETIC_REPO)
    root, name = extract_upload(data, "storefront")
    register_repository(root, name)

    mission_id = "mission-byos-0001"
    store.create_mission(mission_id, title="Inspect storefront",
                         mission_text="Check the storefront code for defects.", repository=name, seed=42)
    pipeline.run_mission(mission_id, "Check the storefront code for defects.", 42, name)

    mission = store.get_mission(mission_id)
    assert mission.status == "completed"
    assert mission.outcome == "success"

    changes = store.get_code_changes(mission_id)
    assert changes == []

    gates = store.get_gates(mission_id)
    by_name = {g.name: g.status for g in gates}
    assert len(by_name) == 7
    # No runner, no fix, no skill: the missing checks must be reported honestly.
    assert by_name["build"] == "na"
    assert by_name["unit_tests"] == "na"
    assert by_name["regression"] == "na"
    assert by_name["architecture"] == "na"
    assert by_name["scope"] == "na"
    assert by_name["code_review"] == "pass"
    assert by_name["security"] == "pass"
    assert gates[0].overall == "ready"


def test_api_upload_and_unavailable_repo_is_rejected():
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    data = _zip(SYNTHETIC_REPO)
    res = client.post(
        "/api/repositories/upload",
        files={"file": ("storefront.zip", data, "application/zip")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "storefront"
    assert body["stats"]["files"] >= 3

    res = client.post("/api/missions", json={
        "title": "No such repo", "mission_text": "anything", "repository": "does-not-exist", "seed": 1,
    })
    assert res.status_code == 400
    assert "does-not-exist" in res.json()["detail"]