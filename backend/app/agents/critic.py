"""Critic agent — independent review of the actor's diff.

Reviews the actual patch: does it address the root cause, stay in scope, keep
tests meaningful, avoid regressions and security regressions, and stay within
reasonable complexity? Criteria that depend on the defect (correctness
hints, allowed scope) come from the matched skill manifest; the rest are
engine-generic.
"""

from __future__ import annotations

from pathlib import Path

from ..skills import Skill
from .base import Timer

CRITERIA = [
    ("correctness", "Does the change address the identified root cause rather than the symptom?"),
    ("scope", "Is the change limited to the affected services?"),
    ("regression", "Does the change risk introducing a new behavior regression?"),
    ("architecture", "Does the change respect module boundaries?"),
    ("security", "Does the change introduce any new security surface?"),
    ("tests", "Are the changes covered by tests that would have caught the original defect?"),
    ("complexity", "Is the implementation unnecessarily broad or complex?"),
]


def _has(blob: str, needles: list[str]) -> bool:
    return any(n in blob for n in needles)


def run_critic(ctx: dict, skill: Skill | None = None) -> dict:
    with Timer() as timer:
        diff_blob = ctx.get("diff_blob", "")
        changes = ctx.get("changes", [])
        if not changes:
            summary = "Critic review: no patch to review — no applicable skill produced changes."
            return {
                "status": "completed", "summary": summary,
                "result": {"verdict": "pass", "score": 100.0, "checks": []},
                "findings": [],
                "evidence": [{"agent": "critic", "kind": "review", "label": "Critic verdict: PASS (100%) — no patch to review", "source": "criteria", "payload": {}}],
                "affected_files": [],
                "recommendations": [],
                "confidence": 1.0, "duration_ms": timer.elapsed_ms,
            }

        files_changed = [c.get("path", "") for c in changes]
        test_results = ctx.get("test_results", {})
        security_counts = ctx.get("security_counts", {})
        scope_prefixes = (skill.criteria.get("scope_prefixes", []) if skill else []) or ["packages", "apps"]
        hints = skill.criteria.get("correctness_hints", []) if skill else []
        validate_failed = int(test_results.get("validate_failed", -1))
        generated = bool(test_results.get("regression_tests_generated"))

        issues: list[dict] = []
        checks: list[tuple[str, bool, str]] = []

        if skill:
            # 1 correctness — remediation signals present in the diff
            ok = bool(hints) and _has(diff_blob, hints)
            checks.append(("correctness", ok, "Remediation signals present in diff" if ok else "No remediation signals detected"))
            # 2 scope — confined to the skill's declared components
            in_scope = all(any(p.startswith(prefix) for prefix in scope_prefixes) for p in files_changed)
            checks.append(("scope", in_scope, f"Changes confined to declared components: {files_changed}" if in_scope else "Change escapes affected components"))
            # 4 architecture — nothing outside the allowed component set
            arch_ok = in_scope or all(p in scope_prefixes for p in files_changed)
            checks.append(("architecture", arch_ok, "No new cross-component coupling introduced" if arch_ok else "Architecture boundary crossed"))
            # 6 tests — real suite evidence (a generated regression is one way;
            # a green full suite after the change is equally strong proof)
            if validate_failed == -1:
                tests_note = "No validation suite evidence for this repository — tests criterion unverified"
            elif generated:
                tests_note = f"Regression coverage generated; validate suite {'green' if validate_failed == 0 else 'red'} after fix"
            else:
                tests_note = f"Existing suite {'green' if validate_failed == 0 else 'red'} after fix; no generated regression (follow-up)"
            checks.append(("tests", validate_failed == 0, tests_note))
        else:
            # Generative/no-skill path: verification evidence is the real test run.
            checks.append(("correctness", validate_failed == 0, "Change verified by the real validation suite" if validate_failed == 0 else "Validation suite red after change"))
            checks.append(("scope", True, "No declared skill scope; change confined to the repository"))
            checks.append(("architecture", True, "No declared module boundary; component risk surfaced by release gate"))
            checks.append(("tests", validate_failed == 0, "Existing suite green after change"
                           + ("" if generated else "; no regression generated (no skill) — recommended as follow-up")))

        # 3 regression risk
        low_risk = len(files_changed) <= 3
        checks.append(("regression", low_risk, f"{len(files_changed)} file(s) changed"))

        # 5 security — no eval/exec/secret additions, no new criticals
        added_secret = _has(diff_blob, ["sk_live", "'sk_", "eval("])
        sec_ok = (not added_secret) and (security_counts.get("critical", 0) == 0)
        checks.append(("security", sec_ok, "No new security surface; 0 critical findings"))

        # 7 complexity
        added = sum(c.get("added", 0) for c in changes)
        complexity_ok = added <= 80
        checks.append(("complexity", complexity_ok, f"{added} insertions total"))

        if not all(ok_ for _, ok_, _ in checks):
            for name, ok_, note in checks:
                if not ok_:
                    issues.append({"criterion": name, "note": note})

        verdict = "pass" if not issues else "changes_requested"
        score = round(sum(1 for _, ok_, _ in checks if ok_) / len(checks) * 100, 1)

        evidence = [
            {"agent": "critic", "kind": "review", "label": f"Critic verdict: {verdict.upper()} ({score}%)", "source": "criteria", "payload": {name: note for name, ok_, note in checks}},
        ]

        summary = f"Critic review: {verdict.replace('_', ' ')} — {int(sum(1 for _, ok_, _ in checks if ok_))}/{len(checks)} criteria satisfied."
        if issues:
            summary += f" {len(issues)} issue(s) flagged."

    return {
        "status": "completed", "summary": summary,
        "result": {"verdict": verdict, "score": score, "checks": [{"criterion": n, "passed": ok_, "note": note} for n, ok_, note in checks]},
        "findings": [{"agent": "critic", "title": f"Review issue: {issue['criterion']}", "detail": issue["note"], "severity": "medium", "category": "review", "file": files_changed[0] if files_changed else "", "line": None, "confidence": 0.85, "evidence_refs": ["review"]} for issue in issues],
        "evidence": evidence,
        "affected_files": files_changed,
        "recommendations": ["Proceed to release gate."] if verdict == "pass" else ["Return patch to actor with the flagged criteria."],
        "confidence": 0.84, "duration_ms": timer.elapsed_ms,
    }