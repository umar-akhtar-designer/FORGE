"""Repository intelligence: indexing, architecture mapping, dependency graph.

This module reads an actual directory tree on disk. Everything it returns is
derived from real files, not fixtures.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .. import config

_IMPORT_RE = re.compile(
    r"""^\s*(?:import(?:[\s\S]*?from)?\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)

_LANG = {
    ".ts": "typescript", ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".json": "json", ".css": "css",
    ".md": "markdown", ".py": "python", ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml", ".html": "html", ".sql": "sql", ".sh": "shell",
}

_TYPES = {"test", "source", "config", "infra", "docs"}

RISK_TERMS = {
    "checkout": 3, "payment": 3, "stripe": 3, "auth": 2, "session": 2,
    "webhook": 2, "order": 2, "secret": 2, "refund": 2, "wallet": 2,
    "billing": 2, "charge": 2, "subscription": 2, "transaction": 2,
}


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def is_ignored(path: str, name: str) -> bool:
    if any(seg in config.EXCLUDED_DIRS for seg in path.split("/")):
        return True
    if name.endswith(tuple(config.EXCLUDED_EXT)):
        return True
    return False


def classify(rel: str) -> str:
    parts = rel.split("/")
    if any("test" in p or "spec" in p for p in parts):
        return "test"
    if rel.endswith(".md"):
        return "docs"
    if ".github" in parts or parts[0] in ("infra", "docker") or rel.startswith("docker"):
        return "infra"
    if rel.endswith((".json", ".toml", ".yaml", ".yml")):
        return "config"
    return "source"


def component_of(rel: str) -> str:
    """Real component boundary: apps/<svc> or packages/<pkg>; otherwise root."""
    parts = rel.split("/")
    if len(parts) >= 2 and parts[0] in ("apps", "packages"):
        return "/".join(parts[:2])
    return "root"


def language(rel: str) -> str:
    suffix = Path(rel).suffix.lower()
    return _LANG.get(suffix, "text")


def extract_imports(content: str) -> list[str]:
    imports: list[str] = []
    text = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    for m in _IMPORT_RE.finditer(text):
        spec = (m.group(1) or m.group(2) or "").strip()
        if spec and not spec.startswith(".") or spec.startswith("."):
            imports.append(spec)
    return imports


def resolve_import(rel: str, spec: str) -> str | None:
    """Best-effort resolution of an import specifier to an in-repo path."""
    if spec.startswith("."):
        cur = Path(rel).parent
        base = spec
        if base.endswith(("/index",)):
            pass
        cand = (Path(cur) / (base + ".ts")).resolve()
        pairs = [
            (cur / base).with_suffix(".ts"),
            (cur / base).with_suffix(".tsx"),
            (cur / base).with_suffix(".js"),
            (cur / base) / "index.ts",
            (cur / base) / "index.tsx",
        ]
        for c in pairs:
            try:
                c.resolve()
            except OSError:
                continue
            return None  # resolution happens later against real files
        return None
    # bare specifier: packages/<name>/src/... or @forge/<name>/...
    m = re.match(r"^(?:@forge/)?([\w-]+)(?:/(.+))?$", spec)
    if m:
        pkg = m.group(1)
        rest = m.group(2) or ""
        return f"packages/{pkg}/src/{rest}".rstrip("/")
    return None


def index_directory(root: Path) -> dict:
    root = root.resolve()
    files: list[dict] = []
    tests: list[dict] = []
    by_path: dict[str, dict] = {}

    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = _relative(p, root)
        if is_ignored(rel, p.name):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        imports = [i for i in extract_imports(content) if i]
        entry = {
            "path": rel,
            "name": p.name,
            "language": language(rel),
            "type": classify(rel),
            "lines": content.count("\n") + 1,
            "size": p.stat().st_size,
            "imports": imports,
        }
        files.append(entry)
        by_path[rel] = entry
        if entry["type"] == "test":
            tests.append(entry)

    return {"root": str(root), "files": files, "by_path": by_path, "tests": tests}


def architecture_map(files: list[dict], by_path: dict) -> dict:
    components: dict[str, set[str]] = defaultdict(set)

    for f in files:
        comp = component_of(f["path"])
        components[comp].add(f["path"])

    nodes, edges, edge_seen = [], [], set()
    order = ["apps/api", "apps/web", "apps/worker", "packages/database", "packages/auth", "packages/payments", "packages/shared"]
    for comp in order:
        if comp in components:
            nodes.append(_component_node(comp, components[comp]))
    for comp in components:
        if comp not in order:
            nodes.append(_component_node(comp, components[comp]))

    edge_set: dict[tuple[str, str], int] = defaultdict(int)
    for f in files:
        src_comp = component_of(f["path"])
        for spec in f.get("imports", []):
            # for relative imports resolve manually against by_path keys
            if spec.startswith("."):
                rel2 = _resolve_relative(f["path"], spec)
                if rel2 and rel2 in by_path:
                    dag = component_of(by_path[rel2]["path"])
                    if dag != src_comp and dag in components:
                        edge_set[(src_comp, dag)] += 1
            else:
                target = resolve_import(f["path"], spec)
                if target:
                    pre = component_of(target)
                    if pre != src_comp and pre in components:
                        edge_set[(src_comp, pre)] += 1

    for (s, t), count in sorted(edge_set.items()):
        edges.append({"source": s, "target": t, "weight": count})

    return {"components": nodes, "edges": edges}


def _resolve_relative(from_rel: str, spec: str) -> str | None:
    cur = Path(from_rel).parent
    base = cur / spec
    if not str(base).startswith("packages") and not str(base).startswith("apps"):
        return None
    for cand in [base.with_suffix(".ts"), base.with_suffix(".tsx"), base.with_suffix(".js"), base / "index.ts", base / "index.tsx"]:
        parts = list(cand.parts)
        if parts and parts[0] in ("packages", "apps"):
            return "/".join(parts)
    return None


def _component_node(name: str, files: set[str]) -> dict:
    rel_files = sorted(files)
    path = next((f for f in rel_files), "")
    risk = 0
    total_lines = 0
    for f in rel_files:
        total_lines += f.get("lines", 0) if isinstance(f, dict) else 0
    for f in rel_files:
        if isinstance(f, dict):
            fp = f.get("path", "")
        else:
            fp = f
        for term, w in RISK_TERMS.items():
            if term in fp.lower():
                risk += w
    return {
        "id": name, "name": name, "kind": "service" if name.startswith("apps") else "package",
        "files": len(rel_files), "risk": min(risk, 9), "lead_file": rel_files[0] if rel_files else "",
    }


def dependencies_manifest(root: Path) -> list[dict]:
    manifests: list[dict] = []
    for p in sorted(root.rglob("package.json")):
        rel = _relative(p, root)
        if is_ignored(rel, p.name):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        manifests.append({"path": rel, "name": data.get("name", rel), "dependencies": deps})
    return manifests


def scan_keywords(root: Path, keywords: list[str]) -> list[dict]:
    """Real keyword scan across source files; returns matches with line numbers."""
    root = root.resolve()
    hits: list[dict] = []
    pats = [re.compile(re.escape(k), re.IGNORECASE) for k in keywords]
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = _relative(p, root)
        if is_ignored(rel, p.name):
            continue
        if language(rel) not in ("typescript", "javascript", "python"):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if any(pat.search(line) for pat in pats):
                hits.append({"path": rel, "line": idx, "content": line.strip()[:140]})
    return hits


def locate_function(root: Path, name: str) -> list[dict]:
    """Find function definitions across the repo (real search)."""
    root = root.resolve()
    out: list[dict] = []
    pat = re.compile(r"\b(?:export\s+)?(?:async\s+)?function\s+" + re.escape(name) + r"\b|const\s+" + re.escape(name) + r"\s*=\s*(?:async\s*)?(?:\([^)]*\)|[\w<>,:\s]+)\s*=>")
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = _relative(p, root)
        if is_ignored(rel, p.name):
            continue
        if language(rel) not in ("typescript", "javascript"):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for idx, line in enumerate(content.splitlines(), 1):
            if pat.search(line):
                out.append({"path": rel, "line": idx, "content": line.strip()[:160]})
    return out


def read_lines(root: Path, rel: str, start: int, count: int = 24) -> list[str]:
    p = (root / rel).resolve()
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[max(start - 1, 0): start - 1 + count]