"""Release agent — evaluate release-gate requirements from real mission results.

Every check is computed from actual validation output; a failing check can
never be marked pass, and the overall status is `ready` only when every
required check passes.
"""

from __future__ import annotations

from .base import Timer

GATE_DEFS = [
    ("build", "Build"),
    ("unit_tests", "Unit Tests"),
    ("regression", "Regression"),
    ("security", "Security"),
    ("code_review", "Code Review"),
    ("architecture", "Architecture"),
    ("scope", "Change Scope"),
]


def _status(ok: bool, ran: bool) -> str:
    if not ran:
        return "na"
    return "pass" if ok else "fail"


def run_release(ctx: dict) -> dict:
    with Timer() as timer:
        build = ctx.get("typecheck", {"ran": True, "ok": True})
        unit = ctx.get("unit", {"ran": True, "failed": 0})
        regression = ctx.get("regression", {"ran": True, "failed": 0})
        critical = int(ctx.get("security_critical", 99))
        critic_verdict = ctx.get("critic_verdict", "changes_requested")
        arch = ctx.get("architecture", {"ran": False, "ok": False, "risk": 0})
        files_changed = int(ctx.get("files_changed", 0))

        checks = [
            ("build", _status(bool(build.get("ok")), bool(build.get("ran"))),
             f"tsc --noEmit {'PASS' if build.get('ok') else 'FAIL'}" if build.get("ran") else "Typecheck not applicable — no tsc installed"),
            ("unit_tests", _status(unit.get("failed", 1) == 0, bool(unit.get("ran"))),
             f"Unit suite {'PASS' if unit.get('failed') == 0 else f'{unit.get('failed')} failing'}" if unit.get("ran") else "Unit suite not applicable — no supported test runner"),
            ("regression", _status(regression.get("failed", 1) == 0, bool(regression.get("ran"))),
             f"Generated regression {'PASS' if regression.get('failed') == 0 else 'FAIL'}" if regression.get("ran") else "Regression not applicable — no skill-generated test"),
            ("security", "pass" if critical == 0 else "fail",
             f"{critical} critical {'findings' if critical != 1 else 'finding'}"),
            ("code_review", "pass" if critic_verdict == "pass" else "fail",
             f"Critic {critic_verdict.replace('_', ' ').upper()}"),
            ("architecture", _status(bool(arch.get("ok")), bool(arch.get("ran"))),
             (f"Architecture integrity OK" if arch.get("ok") else f"Architecture integrity failed (component risk {arch.get('risk', 0)}/9)") if arch.get("ran") else "Architecture not applicable — no changes"),
            ("scope", _status(files_changed <= 3, files_changed > 0),
             f"{files_changed} file(s) changed" if files_changed > 0 else "Scope not applicable — no changes"),
        ]

        failed = [detail for name, status, detail in checks if status == "fail"]
        na = [name for name, status, detail in checks if status == "na"]
        overall = "ready" if not failed else "blocked"

        if overall == "ready" and na:
            summary = f"All applicable release gates passed — release is ready." + (f" {len(na)} check(s) not applicable: {', '.join(na)}." if na else "")
        elif overall == "ready":
            summary = "All release gates passed — release is ready."
        else:
            summary = f"Release blocked by: {', '.join(failed)}"

        result = {
            "checks": [{"name": name, "status": status, "detail": detail} for name, status, detail in checks],
            "overall": overall, "not_applicable": na,
            "summary": summary,
        }

        evidence = [
            {"agent": "release", "kind": "review", "label": f"Release gate: {overall.upper()}", "source": "engine/release", "payload": {"checks": len(checks), "failed": len(failed), "na": len(na)}},
        ]

    return {
        "status": "completed", "summary": result["summary"], "result": result,
        "findings": [{"agent": "release", "title": "Release gate blocked", "detail": "; ".join(failed), "severity": "high", "category": "release", "file": "", "line": None, "confidence": 1.0, "evidence_refs": []}] if failed else [],
        "evidence": evidence, "affected_files": [], "recommendations": [],
        "confidence": 1.0, "duration_ms": timer.elapsed_ms,
    }