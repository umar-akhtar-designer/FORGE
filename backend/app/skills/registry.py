"""Skill registry — pluggable defect playbooks for the FORGE engine.

A *skill* is a folder under ``app/skills/<skill-id>/`` with a ``manifest.json``
plus optional patch and regression templates. Skills declare the *coordinates*
of a defect (which files, which patterns); the engine supplies the generic
probe machinery. Nothing about a specific repository is hardcoded in the
engine agents.

Adding a new autonomous repair capability = adding a skill folder. No engine
changes required.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

SKILLS_DIR = Path(os.environ.get("FORGE_SKILLS_DIR", Path(__file__).resolve().parent))


class Skill:
    def __init__(self, directory: Path, data: dict[str, Any]) -> None:
        self.directory = directory
        self.id = data["id"]
        self.name = data.get("name", self.id)
        self.description = data.get("description", "")
        self.keywords = data.get("keywords", [])
        self.detect = data.get("detect", {"signals": []})
        self.orchestration = data.get("orchestration", "")
        self.callers = data.get("callers", [])
        self.observations = data.get("observations", [])
        self.remediation = data.get("remediation", {"patches": []})
        self.regression = data.get("regression", {})
        self.criteria = data.get("criteria", {})
        self.coverage_gap = data.get("coverage_gap", {})

    def template(self, rel: str) -> str:
        return (self.directory / rel).read_text(encoding="utf-8")

    def reason(self) -> str:
        return self.remediation.get("reason", f"{self.name}: apply remediation.")

    def relevant_files(self) -> list[str]:
        """The full blast radius a debugger should inspect for this skill."""
        out: list[str] = []
        for o in self.observations:
            out.append(o.get("file", ""))
        for p in self.regression.get("entry_points", []):
            out.append(p)
        for p in self.remediation.get("patches", []):
            out.append(p.get("path", ""))
        return _dedupe([f for f in out if f]) or [self.regression.get("dest", "")]

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "detect_signals": len(self.detect.get("signals", [])),
            "observations": len(self.observations),
            "patches": [p.get("path") for p in self.remediation.get("patches", [])],
            "regression_dest": self.regression.get("dest", ""),
        }


def _read(root: Path, rel: str) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _line_of(content: str, needle: str) -> int | None:
    for i, line in enumerate(content.splitlines(), 1):
        if needle in line:
            return i
    return None


def _regex_line(content: str, pattern: str) -> tuple[int | None, re.Match | None]:
    try:
        rx = re.compile(pattern)
    except re.error:
        return None, None
    m = rx.search(content)
    if not m:
        return None, None
    return content[: m.start()].count("\n") + 1, m


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def load_all() -> list[Skill]:
    skills: list[Skill] = []
    if not SKILLS_DIR.exists():
        return skills
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        manifest = d / "manifest.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if "id" not in data:
                continue
            skills.append(Skill(d, data))
        except (OSError, json.JSONDecodeError):
            continue
    return skills


def get(skill_id: str) -> Skill | None:
    return next((s for s in load_all() if s.id == skill_id), None)


def match(skill: Skill, root: Path) -> list[dict]:
    """Real pattern scan: which signals of the skill exist in the workspace?"""
    found: list[dict] = []
    for sig in skill.detect.get("signals", []):
        rel = sig.get("path", "")
        pattern = sig.get("pattern", "")
        content = _read(root, rel)
        line, m = _regex_line(content, pattern)
        present = m is not None
        if not present and not sig.get("optional", False):
            return []
        if present:
            found.append({"path": rel, "pattern": pattern, "line": line, "match": m.group(0) if m else ""})
    return found


def matched(root: Path) -> list[tuple[Skill, list[dict]]]:
    out: list[tuple[Skill, list[dict]]] = []
    for skill in load_all():
        found = match(skill, root)
        if found:
            out.append((skill, found))
    return out


def _method_body(content: str, method_pattern: str) -> tuple[str | None, int | None]:
    line, m = _regex_line(content, method_pattern)
    if m is None:
        return None, None
    head = content[m.start():]
    # Find the opening brace after the signature, then the closing brace at
    # column 0 (2-space indent convention) for a readable body.
    brace = head.find("{")
    if brace == -1:
        return None, line
    rest = head[brace + 1:]
    close = re.search(r"\n  \}", rest)
    end = close.start() if close else (rest.find("}") if "}" in rest else len(rest))
    return rest[: max(end, 0)], line


def _format_detail(template: str, ctx: dict[str, Any]) -> str:
    out = template
    for key, val in ctx.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def run_observations(skill: Skill, root: Path) -> list[dict]:
    """Execute the skill's observations with the generic probe engine.

    Each probe returns a finding with real file/line references from the
    mission workspace. Anything not provable on this repository is simply not
    emitted — no fabricated claims.
    """
    findings: list[dict] = []
    for obs in skill.observations:
        kind = obs.get("kind")
        rel = obs.get("file", "")
        content = _read(root, rel)
        severity = obs.get("severity", "info")
        confidence = float(obs.get("confidence", 0.5))
        ctx: dict[str, Any] = {"file": rel}

        if kind == "missing_guard_in_method":
            method, line = _method_body(content, obs.get("method", ""))
            if method is None:
                continue
            guards = obs.get("guards", [])
            guard_hit = any(g in method for g in guards)
            if guard_hit:
                continue
            ctx["line"] = line
            findings.append({
                "title": obs.get("title", ""),
                "detail": _format_detail(obs.get("detail", ""), ctx),
                "severity": severity, "category": "root-cause", "file": rel,
                "line": line, "confidence": confidence,
                "evidence_refs": [f"{rel}@{line}"],
            })
        elif kind == "line_before":
            la, ma = _regex_line(content, obs.get("needle_a", ""))
            lb, mb = _regex_line(content, obs.get("needle_b", ""))
            if ma is None or mb is None or la is None or lb is None:
                continue
            if la >= lb:
                continue
            ctx["line_a"], ctx["line_b"] = la, lb
            ctx["line"] = la
            findings.append({
                "title": obs.get("title", ""),
                "detail": _format_detail(obs.get("detail", ""), ctx),
                "severity": severity, "category": "root-cause", "file": rel,
                "line": la, "confidence": confidence,
                "evidence_refs": [f"{rel}@{la}", f"{rel}@{lb}"],
            })
        elif kind == "presence":
            line, m = _regex_line(content, obs.get("pattern", ""))
            if m is None:
                continue
            ctx["line"] = line
            findings.append({
                "title": obs.get("title", ""),
                "detail": _format_detail(obs.get("detail", ""), ctx),
                "severity": severity, "category": "root-cause", "file": rel,
                "line": line, "confidence": confidence,
                "evidence_refs": [f"{rel}@{line}"],
            })
    return findings