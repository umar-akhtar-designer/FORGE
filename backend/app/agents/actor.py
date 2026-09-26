"""Actor agent — apply the approved remediation to the mission workspace.

The pristine repository is never modified: every change is written into the
mission workspace copy and the before/after diff is computed against the
pristine source so it is a real, reviewable patch.

The actor is repository-agnostic: it applies whichever patch templates the
matched skill declares. If no skill matched, the actor changes nothing and
says so explicitly.
"""

from __future__ import annotations

from pathlib import Path

from ..intel import workspace as ws
from ..skills import Skill
from .base import Timer


def _diff_stats(diff: str) -> tuple[int, int]:
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    return added, removed


def run_actor(ctx: dict, skill: Skill | None = None) -> dict:
    with Timer() as timer:
        worker_root: Path = Path(ctx["root"])
        pristine_root: Path = Path(ctx["pristine"])
        changes: list[dict] = []

        for patch in (skill.remediation.get("patches", []) if skill else []):
            rel = patch.get("path", "")
            template_rel = patch.get("template", "")
            if not rel or not template_rel:
                continue
            template = skill.template(template_rel)
            before = ws.read_text(pristine_root, rel)
            ws.write_text(worker_root, rel, template)
            after = ws.read_text(worker_root, rel)
            diff = ws.unified_diff(pristine_root, worker_root, rel, before_content=before)
            added, removed = _diff_stats(diff)
            if added == 0 and removed == 0:
                continue
            changes.append({"path": rel, "status": "modified", "added": added, "removed": removed, "diff": diff, "reason": skill.reason()})

        evidence = [
            {"agent": "actor", "kind": "diff",
             "label": f"Patch applied: {len(changes)} file(s), {sum(c['added'] for c in changes)} insertions, {sum(c['removed'] for c in changes)} deletions",
             "source": "workspace", "payload": {"files": [c["path"] for c in changes]}},
        ]

        if changes:
            summary = f"Implemented remediation ({skill.name}) across {len(changes)} file(s): +{sum(c['added'] for c in changes)} -{sum(c['removed'] for c in changes)} lines."
            findings = [{
                "agent": "actor", "title": f"Remediation applied: {skill.name}",
                "detail": skill.reason(), "severity": "info", "category": "implementation",
                "file": changes[0]["path"], "line": None, "confidence": 0.9, "evidence_refs": ["diff"],
            }]
            recommendations = ["Run the full validation suite and the critic review before release."]
            confidence = 0.88
        else:
            summary = "No skill matched this repository — no changes applied."
            findings = []
            recommendations = ["Add a skill manifest for this repository to enable autonomous repair."]
            confidence = 0.0

    return {
        "status": "completed", "summary": summary,
        "result": {"changes": changes, "files_changed": len(changes)},
        "findings": findings, "evidence": evidence,
        "affected_files": [c["path"] for c in changes],
        "recommendations": recommendations,
        "confidence": confidence, "duration_ms": timer.elapsed_ms,
    }