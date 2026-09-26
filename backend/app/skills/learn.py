"""Skill learning — FORGE records a playbook for every bug it fixes with AI.

When a generative (LLM) repair is committed because the real validation suite
passed, FORGE turns that verified fix into a *skill*: a small manifest that
detects the same buggy pattern in future repositories and reproduces the exact
fix deterministically — no LLM needed. This is how the engine grows its own
brain from real, verified work.

The learned skill is keyed by a stable hash of the buggy lines it fixed, so
learning the same defect twice is a no-op. Each learned skill writes a plain
manifest.json + a patch template into ``config.SKILLS_DIR`` (env-overridable),
so it persists across restarts and is reviewable by a human.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .. import config, store
from ..intel.diff import apply_unified_diff
from ..skills.registry import SKILLS_DIR, load_all


def _buggy_lines(diff: str) -> list[str]:
    out = []
    for raw in diff.splitlines():
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("-"):
            line = raw.lstrip("-").rstrip()
            if len(re.sub(r"[^A-Za-z0-9_]", "", line)) >= 12:
                out.append(line)
    return list(dict.fromkeys(out))


def _added_lines(diff: str) -> list[str]:
    """Distinctive lines the fix ADDED — used as critic correctness hints."""
    out = []
    for raw in diff.splitlines():
        if raw.startswith(("+++", "---")):
            continue
        if raw.startswith("+"):
            line = raw.lstrip("+").strip()
            if len(re.sub(r"[^A-Za-z0-9_.]", "", line)) >= 6:
                out.append(line)
    return list(dict.fromkeys(out))[:3]


def _scope_prefixes(rel: str) -> list[str]:
    """Scope that matches BOTH the critic's path-prefix check and the pipeline's
    component-boundary check (``component_of``).

    For ``packages/payments/src/x.ts`` the component is ``packages/payments`` and
    the path starts with it, so both checks agree. For a root-level file such as
    ``src/math.ts`` the component is ``root`` but paths do not start with "root",
    so the first path segment is declared too.
    """
    from ..intel.indexer import component_of

    comp = component_of(rel)
    seg = rel.split("/", 1)[0]
    prefixes = [comp]
    if seg:
        prefixes.append(seg)
        prefixes.append(seg + "/")
    return list(dict.fromkeys(prefixes))


def _fixed_content(mission_id: str, rel: str, pristine: Path, workspace: Path) -> str:
    w = workspace / rel
    if w.is_file():
        try:
            return w.read_text(encoding="utf-8")
        except OSError:
            pass
    base = pristine / rel
    before = base.read_text(encoding="utf-8") if base.is_file() else ""
    diff = next((c.diff for c in store.get_code_changes(mission_id) if c.path == rel), "")
    return apply_unified_diff(before, diff) if diff else before


def _learn_id(buggy: str) -> str:
    return "learned-" + hashlib.sha1(buggy.encode("utf-8")).hexdigest()[:10]


def learn_from_mission(mission_id: str) -> list[str]:
    """Create learned skills from an AI-verified fix. Returns skill ids created."""
    created: list[str] = []
    mission = store.get_mission(mission_id)
    if mission is None:
        return created
    for c in store.get_code_changes(mission_id):
        if "AI repair" not in (c.reason or ""):
            continue
        buggy = _buggy_lines(c.diff)
        if not buggy:
            continue
        skill_id = _learn_id(",".join(buggy))
        if (SKILLS_DIR / skill_id / "manifest.json").exists():
            continue

        pristine = Path("")
        for idx in store.list_repository_indexes():
            if idx.name == mission.repository:
                pristine = Path(idx.path)
                break
        workspace = config.WORKSPACES_DIR / mission_id / "repo"
        fixed = _fixed_content(mission_id, c.path, pristine, workspace)
        if not fixed.strip():
            continue

        dir_path = SKILLS_DIR / skill_id
        dir_path.mkdir(parents=True, exist_ok=True)

        patch_rel = f"patch-{re.sub(r'[^A-Za-z0-9_.-]', '_', c.path)}.txt"
        (dir_path / patch_rel).write_text(fixed, encoding="utf-8")

        hints = _added_lines(c.diff)
        manifest = {
            "id": skill_id,
            "name": f"Learned fix (AI-verified): {c.path}",
            "description": f"Recorded from a generative repair that passed real validation on {mission.repository} for mission {mission_id}.",
            "keywords": [],
            "detect": {"signals": [{"path": c.path, "pattern": re.escape(buggy[0])}]},
            "orchestration": "",
            "observations": [{
                "kind": "presence", "file": c.path, "pattern": re.escape(buggy[0]),
                "title": f"Recurring defect pattern in {c.path}",
                "detail": "This file matches a buggy pattern FORGE previously fixed with an AI repair verified by real tests.",
                "severity": "medium", "confidence": 0.8,
            }],
            "remediation": {
                "reason": "Learned from an AI-generated fix that was verified by the real validation suite.",
                "patches": [{"path": c.path, "template": patch_rel}],
            },
            "regression": {},
            "criteria": {"scope_prefixes": _scope_prefixes(c.path), "correctness_hints": hints},
            "coverage_gap": {},
        }
        (dir_path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        store.add_audit(mission_id, "learn", "skill", f"Learned skill '{skill_id}' from verified AI repair of {c.path}.")
        created.append(skill_id)
    return created


def learned_skill_count() -> int:
    return sum(1 for s in load_all() if s.id.startswith("learned-"))