"""Persistence helpers for mission artifacts.

All writes go through this module so the ORM stays the single source of truth
and the background mission thread is the only writer (guarded by a lock).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from . import orm
from .db import session_scope

_write_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_mission(mission_id: str, title: str, mission_text: str, repository: str, seed: int) -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.Mission(id=mission_id, title=title, mission_text=mission_text, repository=repository, seed=seed, status="queued"))


def start_mission(mission_id: str, workspace: str) -> None:
    with _write_lock, session_scope() as s:
        m = s.get(orm.Mission, mission_id)
        if m:
            m.status = "running"
            m.workspace = workspace
            m.started_at = _now()


def complete_mission(mission_id: str, outcome: str, summary: str, duration_ms: int, error: str = "") -> None:
    with _write_lock, session_scope() as s:
        m = s.get(orm.Mission, mission_id)
        if not m:
            return
        m.status = "failed" if error else "completed"
        m.outcome = outcome
        m.summary = summary
        m.duration_ms = duration_ms
        m.completed_at = _now()
        m.error = error


def set_mission_error(mission_id: str, error: str) -> None:
    with _write_lock, session_scope() as s:
        m = s.get(orm.Mission, mission_id)
        if m:
            m.status = "failed"
            m.error = error
            m.completed_at = _now()


def add_step(mission_id: str, stage: str, name: str, status: str = "pending", message: str = "", order_index: int = 0) -> None:
    with _write_lock, session_scope() as s:
        step = orm.MissionStep(mission_id=mission_id, stage=stage, name=name, status=status, message=message, order_index=order_index)
        if status in ("running", "completed", "failed", "skipped"):
            step.started_at = step.started_at or _now()
        if status in ("completed", "failed", "skipped"):
            step.completed_at = _now()
        s.add(step)


def set_step_status(step_id: int, status: str, message: str = "") -> None:
    with _write_lock, session_scope() as s:
        step = s.get(orm.MissionStep, step_id)
        if step:
            step.status = status
            if message:
                step.message = message
            if status == "running" and not step.started_at:
                step.started_at = _now()
            if status in ("completed", "failed", "skipped"):
                step.completed_at = _now()


def add_agent(mission_id: str, agent: str, role: str, order_index: int, status: str = "queued") -> int:
    with _write_lock, session_scope() as s:
        run = orm.AgentRun(mission_id=mission_id, agent=agent, role=role, status=status, order_index=order_index)
        s.add(run)
        s.flush()
        return int(run.id)


def set_agent_running(run_id: int) -> None:
    with _write_lock, session_scope() as s:
        run = s.get(orm.AgentRun, run_id)
        if run:
            run.status = "running"
            run.started_at = _now()


def complete_agent(run_id: int, payload: dict) -> None:
    with _write_lock, session_scope() as s:
        run = s.get(orm.AgentRun, run_id)
        if not run:
            return
        run.status = payload.get("status", "completed")
        run.summary = payload.get("summary", "")
        run.result_json = payload.get("result", {})
        run.findings_json = payload.get("findings", [])
        run.evidence_json = payload.get("evidence", [])
        run.affected_files = payload.get("affected_files", [])
        run.recommendations = payload.get("recommendations", [])
        run.confidence = float(payload.get("confidence", 0.0))
        run.duration_ms = payload.get("duration_ms", 0)
        run.completed_at = _now()


def add_finding(mission_id: str, agent: str, title: str, detail: str, severity: str, category: str, file: str, line: int | None, confidence: float, evidence_refs: list[str] | None = None) -> int:
    with _write_lock, session_scope() as s:
        f = orm.Finding(mission_id=mission_id, agent=agent, title=title, detail=detail, severity=severity, category=category, file=file, line=line, confidence=confidence, evidence_refs=evidence_refs or [])
        s.add(f)
        s.flush()
        return int(f.id)


def add_evidence(mission_id: str, agent: str, kind: str, label: str, source: str = "", payload: dict | None = None) -> int:
    with _write_lock, session_scope() as s:
        e = orm.Evidence(mission_id=mission_id, agent=agent, kind=kind, label=label, source=source, payload=payload or {})
        s.add(e)
        s.flush()
        return int(e.id)


def add_code_change(mission_id: str, path: str, status: str, added: int, removed: int, diff: str, reason: str) -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.CodeChange(mission_id=mission_id, path=path, status=status, added=added, removed=removed, diff=diff, reason=reason))


def add_test(mission_id: str, suite: str, phase: str, path: str, name: str, status: str, duration_ms: int, detail: str = "") -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.TestRun(mission_id=mission_id, suite=suite, phase=phase, path=path, name=name, status=status, duration_ms=duration_ms, detail=detail))


def add_security_finding(mission_id: str, rule: str, severity: str, title: str, path: str, line: int | None, description: str, remediation: str) -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.SecurityFinding(mission_id=mission_id, rule=rule, severity=severity, title=title, path=path, line=line, description=description, remediation=remediation))


def add_review(mission_id: str, reviewer: str, verdict: str, score: float, summary: str, issues: list[dict], reviewed_files: list[str]) -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.Review(mission_id=mission_id, reviewer=reviewer, verdict=verdict, score=score, summary=summary, issues_json=issues, reviewed_files=reviewed_files))


def add_release_gate(mission_id: str, name: str, status: str, detail: str, order_index: int, overall: str) -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.ReleaseGate(mission_id=mission_id, name=name, status=status, detail=detail, order_index=order_index, overall=overall, checked_at=_now()))


def add_metric(mission_id: str, key: str, label: str, value: float, unit: str, source: str, order_index: int) -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.Metric(mission_id=mission_id, key=key, label=label, value=value, unit=unit, source=source, order_index=order_index))


def add_audit(mission_id: str, agent: str, category: str, message: str) -> None:
    with _write_lock, session_scope() as s:
        s.add(orm.AuditEvent(mission_id=mission_id, agent=agent, category=category, message=message, at=_now()))


def save_repository_index(name: str, path: str, stats: dict, files: list, tests: list, architecture: dict, dependencies: list) -> None:
    with _write_lock, session_scope() as s:
        existing = s.get(orm.RepositoryIndex, name)
        if existing:
            existing.stats, existing.files, existing.tests = stats, files, tests
            existing.architecture, existing.dependencies = architecture, dependencies
            existing.indexed_at = _now()
        else:
            s.add(orm.RepositoryIndex(name=name, path=path, stats=stats, files=files, tests=tests, architecture=architecture, dependencies=dependencies))


# ---- reads ----

def get_mission(mission_id: str) -> orm.Mission | None:
    with session_scope() as s:
        return s.get(orm.Mission, mission_id)


def list_missions(limit: int = 50) -> list[orm.Mission]:
    with session_scope() as s:
        return list(s.query(orm.Mission).order_by(orm.Mission.created_at.desc()).limit(limit).all())


def get_steps(mission_id: str) -> list[orm.MissionStep]:
    with session_scope() as s:
        return list(s.query(orm.MissionStep).filter_by(mission_id=mission_id).order_by(orm.MissionStep.order_index).all())


def get_agents(mission_id: str) -> list[orm.AgentRun]:
    with session_scope() as s:
        return list(s.query(orm.AgentRun).filter_by(mission_id=mission_id).order_by(orm.AgentRun.order_index).all())


def get_findings(mission_id: str) -> list[orm.Finding]:
    with session_scope() as s:
        return list(s.query(orm.Finding).filter_by(mission_id=mission_id).order_by(orm.Finding.id).all())


def get_evidence(mission_id: str) -> list[orm.Evidence]:
    with session_scope() as s:
        return list(s.query(orm.Evidence).filter_by(mission_id=mission_id).order_by(orm.Evidence.id).all())


def get_code_changes(mission_id: str) -> list[orm.CodeChange]:
    with session_scope() as s:
        return list(s.query(orm.CodeChange).filter_by(mission_id=mission_id).order_by(orm.CodeChange.path).all())


def get_tests(mission_id: str) -> list[orm.TestRun]:
    with session_scope() as s:
        return list(s.query(orm.TestRun).filter_by(mission_id=mission_id).order_by(orm.TestRun.id).all())


def get_security(mission_id: str) -> list[orm.SecurityFinding]:
    with session_scope() as s:
        return list(s.query(orm.SecurityFinding).filter_by(mission_id=mission_id).order_by(orm.SecurityFinding.severity, orm.SecurityFinding.id).all())


def get_reviews(mission_id: str) -> list[orm.Review]:
    with session_scope() as s:
        return list(s.query(orm.Review).filter_by(mission_id=mission_id).order_by(orm.Review.id).all())


def get_gates(mission_id: str) -> list[orm.ReleaseGate]:
    with session_scope() as s:
        return list(s.query(orm.ReleaseGate).filter_by(mission_id=mission_id).order_by(orm.ReleaseGate.order_index).all())


def get_metrics(mission_id: str) -> list[orm.Metric]:
    with session_scope() as s:
        return list(s.query(orm.Metric).filter_by(mission_id=mission_id).order_by(orm.Metric.order_index).all())


def get_audit(mission_id: str) -> list[orm.AuditEvent]:
    with session_scope() as s:
        return list(s.query(orm.AuditEvent).filter_by(mission_id=mission_id).order_by(orm.AuditEvent.at).all())


def get_repository_index(name: str) -> orm.RepositoryIndex | None:
    with session_scope() as s:
        return s.get(orm.RepositoryIndex, name)


def list_repository_indexes() -> list[orm.RepositoryIndex]:
    with session_scope() as s:
        return list(s.query(orm.RepositoryIndex).order_by(orm.RepositoryIndex.indexed_at.desc()).all())


MOVERS = {
    "metrics": get_metrics, "tests": get_tests, "evidence": get_evidence,
    "findings": get_findings, "security": get_security, "reviews": get_reviews,
    "gates": get_gates, "changes": get_code_changes, "audit": get_audit,
}