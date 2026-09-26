"""Shared agent machinery: timing, subprocess runners, structured outputs."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any

AGENT_ROLES = {
    "architect": "Map repository structure, dependencies and blast radius.",
    "debugger": "Trace failures and identify the root cause with evidence.",
    "security": "Scan for security regressions and high-risk patterns.",
    "tester": "Inspect coverage, generate regression tests and execute validation.",
    "actor": "Implement the approved fix in the mission workspace.",
    "critic": "Independently review the implementation.",
    "release": "Evaluate release-gate requirements for the final go/no-go.",
}

STAGE_ORDER = ["init", "plan", "investigate", "root_cause", "implement", "validate", "critic", "release", "report"]


def run_cmd(cmd: list[str], cwd: str, timeout: int = 180) -> tuple[int, str, str]:
    env = dict(os.environ)
    env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def parse_vitest(stdout: str) -> tuple[int, int, int]:
    """Parse vitest summary: (test_files, total_tests, failed_tests)."""
    files_m = re.search(r"Test Files\s+(\d+) (?:passed|failed)", stdout)
    tests_m = re.search(r"Tests\s+(\d+) (?:passed|failed)", stdout)
    total = int(tests_m.group(1)) if tests_m else 0
    failed = 0
    m = re.search(r"Tests\s+\d+ passed \|\s*(\d+) failed", stdout)
    if not m:
        m = re.search(r"Tests\s+(\d+) failed", stdout)
    if m:
        failed = int(m.group(1))
    files = int(files_m.group(1)) if files_m else 0
    return files, total, failed


class Timer:
    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)

    elapsed_ms = 0


def vector(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a structured agent result dict."""
    return {
        "status": payload.get("status", "completed"),
        "summary": payload.get("summary", ""),
        "result": payload.get("result", {}),
        "findings": payload.get("findings", []),
        "evidence": payload.get("evidence", []),
        "affected_files": payload.get("affected_files", []),
        "recommendations": payload.get("recommendations", []),
        "confidence": float(payload.get("confidence", 0.0)),
        "duration_ms": int(payload.get("duration_ms", 0)),
    }