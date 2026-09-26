"""Bring-Your-Own-Software: safe upload extraction.

Security posture for uploaded archives:
  * members are validated before anything is written (no absolute paths, no
    ``..`` traversal, no symlinks);
  * entry count and total uncompressed size are capped (zip-bomb guard);
  * archives with no usable files are rejected;
  * extraction happens inside a per-upload private directory under
    ``config.UPLOADS_DIR``.

After extraction the project root is detected: if the archive wraps a single
top-level folder, that folder is the root; otherwise the extraction root is
used. No code inside the archive is ever executed here.
"""

from __future__ import annotations

import io
import re
import shutil
import uuid
import zipfile
from pathlib import Path

from .. import config

_SKIP_PREFIXES = ("__MACOSX/", ".DS_Store")
_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _slug(name: str) -> str:
    base = Path(name).stem.lower()
    base = _SLUG_RE.sub("-", base).strip("-")
    return (base[:40] or "repo")


def _safe_member(dest: Path, info: zipfile.ZipInfo) -> Path | None:
    """Return the resolved target path, or None if the member is unsafe."""
    raw = info.filename.replace("\\", "/")
    if raw.startswith(_SKIP_PREFIXES):
        return None
    if info.is_dir():
        return None
    if raw == "" or raw.startswith("/") or ":" in raw.split("/")[0]:
        return None
    target = (dest / raw).resolve()
    try:
        target.relative_to(dest.resolve())
    except ValueError:
        return None
    return target


def extract_upload(data: bytes, suggested_name: str = "repo") -> tuple[Path, str]:
    """Extract an uploaded zip safely.

    Returns ``(project_root, repo_name)``. Raises ``ValueError`` when the
    archive is empty, malformed, too large or entirely unsafe.
    """
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not data:
        raise ValueError("Uploaded archive is empty")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise ValueError(f"Archive exceeds {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")

    upload_id = uuid.uuid4().hex[:12]
    name = _slug(suggested_name)
    dest = config.UPLOADS_DIR / f"{name}-{upload_id}"
    dest.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) > config.MAX_ZIP_ENTRIES:
                raise ValueError(f"Archive has too many entries ({len(infos)})")
            total = 0
            for info in infos:
                total += (info.file_size or 0)
                if total > config.MAX_UNCOMPRESSED_BYTES:
                    raise ValueError("Archive exceeds uncompressed size limit")
                target = _safe_member(dest, info)
                if target is None:
                    continue
                src = zf.open(info)
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with src, target.open("wb") as out:
                        shutil.copyfileobj(src, out, length=1024 * 1024)
                finally:
                    src.close()

        written = sorted(p for p in dest.rglob("*") if p.is_file())
        if not written:
            raise ValueError("Archive contained no usable files")
        root = _project_root(dest)
        return root, name
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def _project_root(dest: Path) -> Path:
    """If the archive wraps a single top-level folder, use it as the root."""
    dirs = [d for d in sorted(dest.iterdir()) if d.is_dir()]
    files = [p for p in dest.iterdir() if p.is_file()]
    if not files and len(dirs) == 1:
        return dirs[0]
    return dest


def register_repository(root: Path, name: str) -> dict:
    """Index an uploaded repo into the store so missions can target it."""
    from .. import store
    from ..intel.indexer import architecture_map, dependencies_manifest, index_directory

    files: list = []
    tests: list = []
    architecture: dict = {}
    dependencies: list = []
    try:
        files = index_directory(root)
        architecture = architecture_map(files["files"], files["by_path"])
        files["architecture"] = architecture
        tests = files["tests"]
        dependencies = dependencies_manifest(root)
    except Exception:  # noqa: BLE001 — pipeline re-indexes at run time anyway
        files = {"files": [], "tests": [], "by_path": {}}
    stats = {
        "files": len(files.get("files", [])),
        "lines": sum(f["lines"] for f in files.get("files", [])),
        "tests": len(tests),
        "components": len(architecture.get("components", [])) if architecture else 0,
    }
    store.save_repository_index(name, str(root), stats, files.get("files", []), tests, architecture, dependencies)
    return {"name": name, "path": str(root), "stats": stats, "files": files.get("files", []), "tests": tests, "architecture": architecture, "dependencies": dependencies}


def import_zip_bytes(data: bytes, suggested_name: str = "repo") -> tuple[Path, str]:
    """Convenience used by tests and the API."""
    return extract_upload(data, suggested_name)