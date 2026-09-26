"""Tester agent — coverage analysis, regression generation, execution.

Two phases:
  * investigate — run the existing unit suite, close the coverage gap the
    matched skill declares, write the skill's deterministic regression test,
    and run it (expect it to FAIL on the shipped defect).
  * validate   — run the full suite (unit + regression) and a strict typecheck
    on the changed workspace (expect everything to be green).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from ..intel import workspace as ws
from ..skills import Skill
from .base import Timer, parse_vitest, run_cmd


def _vitest_bin(root: Path):
    return str(root / "node_modules" / ".bin" / "vitest")


def _tsc_bin(root: Path):
    return str(root / "node_modules" / ".bin" / "tsc")


def _has_pytest_config(root: Path) -> bool:
    for rel in ("pyproject.toml", "setup.cfg", "pytest.ini", "tox.ini"):
        p = root / rel
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "[tool.pytest" in text or "[tool:pytest]" in text or rel == "pytest.ini":
            return True
    return False


def detect_runner(root: Path) -> str | None:
    """Detect an installed test runner so tests are real — or honestly skipped.

    Node runners require their binaries to actually be installed (``node_modules/
    .bin``). Go and Cargo additionally require the toolchain on PATH; without it
    we report honestly rather than pretending to run tests.
    """
    bin_dir = root / "node_modules" / ".bin"
    if (bin_dir / "vitest").exists():
        return "vitest"
    if (bin_dir / "jest").exists():
        return "jest"
    if (root / "requirements.txt").exists() or _has_pytest_config(root):
        return "pytest"
    if (root / "go.mod").exists() and shutil.which("go"):
        return "go"
    if (root / "Cargo.toml").exists() and shutil.which("cargo"):
        return "cargo"
    return None


def _parse_go_events(data: str) -> tuple[list[dict], int, int]:
    """Parse ``go test -json -v`` newline-delimited event stream.

    Each passing/failing test emits an event: {Action: "pass"|"fail", Package,
    Test}. Package is the import path; we report its directory as the path.
    """
    rows: list[dict] = []
    for line in data.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("Action") in ("pass", "fail") and ev.get("Test"):
            status = "passed" if ev["Action"] == "pass" else "failed"
            pkg = str(ev.get("Package", "."))
            rows.append({"path": pkg, "name": str(ev["Test"]), "status": status})
    return rows, len(rows), sum(1 for r in rows if r["status"] == "failed")


def _skipped_runs():
    return {"code": None, "files": 0, "total": 0, "failed": 0, "stdout": "", "stderr": "", "rows": [], "ran": False}


def _parse_json_rows(out_file: Path, real_root: str) -> list[dict]:
    try:
        data = json.loads(out_file.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return []
    rows = []
    for suite in data.get("testResults", []):
        raw = str(suite.get("name", ""))
        rel = os.path.realpath(raw).replace(real_root + "/", "").replace("\\", "/")
        for a in suite.get("assertionResults", []):
            rows.append({"path": rel, "name": str(a.get("fullName", a.get("title", ""))), "status": str(a.get("status", "passed"))})
    return rows


def _parse_test_rows(stdout: str) -> list[dict]:
    rows = []
    for line in stdout.splitlines():
        m = re.match(r"\s*(?:✓|×)\s+([\w/.\-]+\.test\.ts)\s+>\s+(?:[\w\s()\-/]+\s+>\s+)?(.+)$", line)
        if m:
            rows.append({"path": m.group(1), "name": m.group(2).strip(), "status": "passed" if line.strip().startswith("✓") else "failed"})
        else:
            m2 = re.match(r"\s*FAIL\s+([\w/.\-]+\.test\.ts)\s+>\s+(.+)", line)
            if m2:
                rows.append({"path": m2.group(1), "name": m2.group(2).strip(), "status": "failed"})
    return rows


def run_unit_suite(root: Path, suite_dir: str = "tests/unit") -> dict:
    """vitest suite run — the deterministic runner used by the demo repo."""
    out_file = Path(tempfile.mkdtemp(prefix="forge-vitest-")) / "vitest-results.json"
    code, out, err = run_cmd([_vitest_bin(root), "run", suite_dir, "--reporter=json", f"--outputFile={out_file}"], str(root), timeout=240)

    real_root = os.path.realpath(str(root))
    rows = _parse_json_rows(out_file, real_root) or _parse_test_rows(out)
    data = {}
    try:
        data = json.loads(out_file.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        pass
    if "numTotalTests" in data:
        files, total, failed = data.get("numTotalTestSuites", 0), data.get("numTotalTests", 0), data.get("numFailedTests", 0)
    else:
        files, total, failed = parse_vitest(out)
    return {
        "code": code, "files": files, "total": total, "failed": failed,
        "stdout": out, "stderr": err, "rows": rows, "ran": True,
    }


def run_jest(root: Path, suite_dir: str = "tests") -> dict:
    out_file = Path(tempfile.mkdtemp(prefix="forge-jest-")) / "jest-results.json"
    cmd = ["npx", "--no-install", "jest", "--json", "--outputFile", str(out_file)]
    if suite_dir and suite_dir != ".":
        cmd.append(suite_dir)
    code, out, err = run_cmd(cmd, str(root), timeout=240)
    real_root = os.path.realpath(str(root))
    rows = _parse_json_rows(out_file, real_root)
    total = sum(1 for r in rows)
    failed = sum(1 for r in rows if r["status"] in ("failed",))
    return {"code": code, "files": len({r["path"] for r in rows}), "total": total, "failed": failed,
            "stdout": out, "stderr": err, "rows": rows, "ran": True}


def run_pytest(root: Path) -> dict:
    code, out, err = run_cmd(["python3", "-m", "pytest", "-v", "--tb=no"], str(root), timeout=240)
    rows = []
    for line in out.splitlines():
        m = re.match(r"\s*(.+\.py)::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)", line.strip())
        if m:
            rows.append({"path": m.group(1).rstrip("/"), "name": m.group(2), "status": "passed" if m.group(3) == "PASSED" else "failed"})
    total = len(rows)
    failed = sum(1 for r in rows if r["status"] != "passed")
    return {"code": code, "files": len({r["path"] for r in rows}), "total": total, "failed": failed,
            "stdout": out, "stderr": err, "rows": rows, "ran": True}


def run_go(root: Path) -> dict:
    """``go test -json -v ./...`` — real Go tests, parsed from the event stream."""
    code, out, err = run_cmd(["go", "test", "-json", "-v", "./..."], str(root), timeout=300)
    rows, total, failed = _parse_go_events(out)
    return {"code": code, "files": len({r["path"] for r in rows}) or (1 if total else 0), "total": total, "failed": failed,
            "stdout": out, "stderr": err, "rows": rows, "ran": True}


def _parse_cargo(stdout: str) -> tuple[list[dict], int, int]:
    rows: list[dict] = []
    for line in stdout.splitlines():
        m = re.match(r"\s*test\s+([\w:_/\-]+)\s+\.\.\.\s+(ok|FAILED)", line.strip())
        if m:
            rows.append({"path": ".", "name": m.group(1), "status": "passed" if m.group(2) == "ok" else "failed"})
    if not rows:
        m = re.search(r"test result: (?:ok|FAILED)\. (\d+) passed;\s*(\d+) failed", stdout)
        if m:
            return [], int(m.group(1)) + int(m.group(2)), int(m.group(2))
    return rows, len(rows), sum(1 for r in rows if r["status"] == "failed")


def run_cargo(root: Path) -> dict:
    """``cargo test`` — real Rust tests, parsed from the harness output."""
    code, out, err = run_cmd(["cargo", "test", "--quiet"], str(root), timeout=300)
    rows, total, failed = _parse_cargo(out + err)
    return {"code": code, "files": 1 if total else 0, "total": total, "failed": failed,
            "stdout": out, "stderr": err, "rows": rows, "ran": True}


def run_tests(root: Path, runner: str | None, suite_dir: str = "tests") -> dict:
    if runner is None:
        return _skipped_runs()
    if runner == "vitest":
        return run_unit_suite(root, suite_dir)
    if runner == "jest":
        return run_jest(root, suite_dir)
    if runner == "pytest":
        return run_pytest(root)
    if runner == "go":
        return run_go(root)
    if runner == "cargo":
        return run_cargo(root)
    return _skipped_runs()


def phase_investigate(ctx: dict, skill: Skill | None = None) -> dict:
    with Timer() as timer:
        root: Path = Path(ctx["root"])
        runner = detect_runner(root)
        unit_dir = "tests/unit" if (root / "tests" / "unit").is_dir() else "tests"
        unit = run_tests(root, runner, unit_dir)
        tests_recorded = unit["rows"]

        gap = []
        if skill and runner == "vitest":
            dest = skill.regression.get("dest", "")
            dest_dir = str(Path(dest).parent)
            template_rel = skill.regression.get("template", "")
            if dest and template_rel:
                has_regression = (root / dest).exists()
                if not has_regression:
                    template = skill.template(template_rel)
                    ws.write_text(root, dest, template)
                reg = run_unit_suite(root, dest_dir)
                reg_rows = reg["rows"]
            else:
                reg, reg_rows = {"total": 0, "failed": 0, "rows": []}, []
            for row in tests_recorded:
                if dest in row["path"]:
                    reg_rows = [row] + reg_rows
            if not any(dest in r["path"] for r in (tests_recorded + reg_rows)):
                cg = skill.coverage_gap
                gap.append({
                    "title": cg.get("title", f"Missing regression coverage for {skill.name}"),
                    "detail": cg.get("detail", "The matched skill requires a deterministic regression test that reproduces the defect."),
                    "severity": "medium", "file": cg.get("file", dest or ""), "line": None,
                })
        elif runner is None:
            gap.append({
                "title": "No supported test runner found",
                "detail": "No vitest, jest, pytest, go or cargo runner was detected on this repository, so no tests were executed. FORGE reports this honestly instead of inventing results.",
                "severity": "medium", "file": "", "line": None,
            })
            if skill:
                gap.append({
                    "title": "Regression not generated — runner is incompatible",
                    "detail": "The matched skill declares a vitest regression template, which cannot run on this repository.",
                    "severity": "medium", "file": "", "line": None,
                })
            reg, reg_rows = {"total": 0, "failed": 0, "rows": []}, []
        else:
            reg, reg_rows = {"total": 0, "failed": 0, "rows": []}, []
            gap.append({
                "title": "No regression coverage declared",
                "detail": "No skill matched this repository, so no targeted regression test was generated.",
                "severity": "low", "file": "", "line": None,
            })

        recordings = tests_recorded + reg_rows

        affected = list(dict.fromkeys([r["path"] for r in recordings]))

        findings = []
        for g in gap:
            findings.append({"agent": "tester", "title": g["title"], "detail": g["detail"], "severity": g["severity"], "category": "coverage", "file": g["file"], "line": g["line"], "confidence": 0.8, "evidence_refs": ["regression-run"]})
        if skill and reg["failed"] > 0 and reg.get("total", 0) > 0:
            dest = skill.regression.get("dest", "")
            findings.append({"agent": "tester", "title": f"Generated regression test reproduces the defect ({reg['failed']} failing)", "detail": f"{dest} deterministically reproduces the {skill.name.lower()}. Before the fix it fails; after the fix it must pass.", "severity": "high", "category": "regression", "file": dest, "line": None, "confidence": 0.95, "evidence_refs": ["regression-run"]})

        evidence = []
        if runner:
            evidence.append({"agent": "tester", "kind": "test", "label": f"{runner} suite: {unit['total']} tests, {unit['failed']} failed", "source": unit_dir, "payload": {"total": unit["total"], "failed": unit["failed"]}})
        else:
            evidence.append({"agent": "tester", "kind": "test", "label": "No test runner detected — tests not executed", "source": "", "payload": {"ran": False}})
        if skill and runner == "vitest":
            dest = skill.regression.get("dest", "")
            evidence.append({"agent": "tester", "kind": "test", "label": f"Regression (generated): {reg['total']} tests, {reg['failed']} failed", "source": dest, "payload": {"total": reg["total"], "failed": reg["failed"]}})

        gen_part = f"Generated regression fails on current codebase ({reg['failed']} failing)." if skill and runner == "vitest" else ("No test runner detected — tests not executed." if runner is None else "No target regression generated.")
        summary = f"Coverage window closed. {runner.title() if runner else 'No runner'} suite ({unit['total']} tests); {gen_part}"

    return {
        "status": "completed", "summary": summary,
        "result": {
            "phase": "investigate", "runner": runner,
            "unit": {"total": unit["total"], "failed": unit["failed"], "files": unit["files"], "ran": bool(runner)},
            "regression": {"total": reg.get("total", 0), "failed": reg.get("failed", 0)},
            "generated": skill.regression.get("dest", "") if skill and runner == "vitest" else "",
            "tests": recordings,
        },
        "findings": findings, "evidence": evidence,
        "affected_files": affected,
        "recommendations": ["Run the full suite after the fix to confirm the regression now passes.", "Keep the generated regression test as permanent coverage."] if skill else ["Install a supported test runner (vitest, jest, pytest, go, cargo) to enable real test execution."],
        "confidence": 0.9, "duration_ms": timer.elapsed_ms,
    }


def phase_validate(ctx: dict) -> dict:
    with Timer() as timer:
        root: Path = Path(ctx["root"])
        runner = detect_runner(root)
        full = run_tests(root, runner, "tests")

        tsc_present = (root / "node_modules" / ".bin" / "tsc").exists()
        tc_code: int | None
        if tsc_present:
            tc_code_t, tc_out, tc_err = run_cmd([_tsc_bin(root), "--noEmit"], str(root), timeout=240)
            tc_code = tc_code_t
        else:
            tc_code, tc_out, tc_err = None, "", "tsc not installed for this repository; typecheck not executed."

        if full["ran"]:
            recordings = full["rows"] + ([{"path": "typecheck", "name": "tsc --noEmit", "status": "passed" if tc_code == 0 else "failed"}] if tsc_present else [])
        else:
            recordings = ([{"path": "typecheck", "name": "tsc --noEmit", "status": "passed" if tc_code == 0 else "failed"}] if tsc_present else [])
        affected = list(dict.fromkeys([r["path"] for r in full["rows"]]))

        problems = []
        if full["ran"] and full["failed"] > 0:
            problems.append(f"Full suite: {full['failed']} failing")
        if tsc_present and tc_code != 0:
            problems.append(f"typecheck exit {tc_code}")
        findings = [] if not problems else [{
            "agent": "tester", "title": "Validation caught a problem", "detail": "; ".join(problems) or "validation failed.", "severity": "high", "category": "validation", "file": "", "line": None, "confidence": 0.9, "evidence_refs": ["validate-run"],
        }]

        evidence = []
        if runner:
            evidence.append({"agent": "tester", "kind": "test", "label": f"Full suite after fix: {full['total']} tests, {full['failed']} failed", "source": "tests", "payload": {"total": full["total"], "failed": full["failed"]}})
        if tsc_present:
            evidence.append({"agent": "tester", "kind": "command", "label": f"Typecheck: {'PASS' if tc_code == 0 else 'FAIL'}", "source": "tsc --noEmit", "payload": {"exit_code": tc_code, "detail": (tc_out or tc_err)[-400:]}})
        else:
            evidence.append({"agent": "tester", "kind": "command", "label": "Typecheck: not applicable", "source": "tsc --noEmit", "payload": {"exit_code": None, "detail": tc_err}})

        if runner and full["ran"]:
            summary = f"Validation: full suite {full['total']} tests ({full['failed']} failed)" + (f" and typecheck {'passed' if tc_code == 0 else 'failed'}." if tsc_present else " (no typecheck tooling).")
        else:
            summary = "Validation: tests not executed — no supported test runner. " + ("Typecheck passed." if tsc_present and tc_code == 0 else ("Typecheck not applicable." if not tsc_present else "Typecheck failed."))
        summary = summary.rstrip()

    return {
        "status": "completed", "summary": summary,
        "result": {"phase": "validate", "tests": recordings, "full": {"total": full["total"], "failed": full["failed"], "files": full["files"], "ran": full["ran"]}, "typecheck": {"exit_code": tc_code, "ran": tsc_present}},
        "findings": findings, "evidence": evidence,
        "affected_files": affected,
        "recommendations": [] if not problems else ["Resolve failing tests before releasing."],
        "confidence": 0.95, "duration_ms": timer.elapsed_ms,
    }


def run_tester(ctx: dict, skill: Skill | None = None) -> dict:
    if ctx.get("phase") == "validate":
        return phase_validate(ctx)
    return phase_investigate(ctx, skill)