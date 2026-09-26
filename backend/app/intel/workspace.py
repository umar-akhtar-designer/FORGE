"""Mission workspace management.

Each mission gets a private copy of the target repository so the Actor can
write real changes without mutating the pristine source. When the source ships
node_modules, the workspace copy shares them (symlink) so tests run fast.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .. import config


def create_workspace(mission_id: str, src: Path) -> Path:
    config.ensure_dirs()
    if not src.is_dir():
        raise ValueError(f"source repository is not a directory: {src}")
    dst = config.WORKSPACES_DIR / mission_id / "repo"
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("node_modules", ".git", ".next"))
    nm = src / "node_modules"
    if nm.exists():
        link = dst / "node_modules"
        if not link.exists():
            link.symlink_to(nm, target_is_directory=True)
    return dst


def clean_workspace(mission_id: str) -> None:
    dst = config.WORKSPACES_DIR / mission_id
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)


def rel_file(root: Path, rel: str) -> Path:
    return (root / rel).resolve()


def write_text(root: Path, rel: str, content: str) -> Path:
    p = rel_file(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def read_text(root: Path, rel: str) -> str:
    return rel_file(root, rel).read_text(encoding="utf-8")


def unified_diff(root_before: Path, root_after: Path, rel: str, before_content: str | None = None) -> str:
    """Real unified diff via difflib between source and workspace copy."""
    import difflib

    a = (before_content if before_content is not None else read_text(root_before, rel)).splitlines(keepends=True)
    b = read_text(root_after, rel).splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm="\n"))