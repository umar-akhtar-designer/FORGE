import os
import shutil
import tempfile

_tmp = tempfile.mkdtemp(prefix="forge-tests-")
os.environ.setdefault("FORGE_DB_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("FORGE_WORKSPACES_DIR", f"{_tmp}/workspaces")
os.environ.setdefault("FORGE_UPLOADS_DIR", f"{_tmp}/uploads")
os.environ.setdefault("FORGE_SKILL_LEARNING", "true")

import pytest

from app.db import get_engine, init_db
from app.orm import Base

_SHIPPED_SKILLS = (
    __import__("pathlib").Path(__file__).resolve().parent.parent
    / "app" / "skills"
)


def _fresh_skills_dir() -> str:
    """Per-test skills dir seeded with the author-written skills.

    Each test gets its own registry so learned playbooks can never bleed
    between tests (learning-from-fix in one test must not make the next
    test's mission deterministic via a now-matching skill).
    """
    dir_path = tempfile.mkdtemp(prefix="forge-skills-")
    for entry in _SHIPPED_SKILLS.iterdir():
        if entry.is_dir() and not entry.name.startswith(("__", "learned-")):
            shutil.copytree(entry, f"{dir_path}/{entry.name}", dirs_exist_ok=True)
    return dir_path


@pytest.fixture(autouse=True)
def _db(monkeypatch):
    init_db()
    fresh = _fresh_skills_dir()
    monkeypatch.setenv("FORGE_SKILLS_DIR", fresh)
    from app.skills import learn, registry
    monkeypatch.setattr(registry, "SKILLS_DIR", __import__("pathlib").Path(fresh))
    monkeypatch.setattr(learn, "SKILLS_DIR", __import__("pathlib").Path(fresh))
    from app.api import security
    security._invocations.clear()
    yield
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())