"""FORGE ORM schema (SQLAlchemy 2.x typed style)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


def _json_default(obj):
    return json.dumps(obj, default=str)


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled Mission")
    mission_text: Mapped[str] = mapped_column(Text, default="")
    repository: Mapped[str] = mapped_column(String(64), default="forgemart")
    seed: Mapped[int] = mapped_column(Integer, default=0)
    workspace: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued|running|completed|failed|blocked
    outcome: Mapped[str] = mapped_column(String(32), default="")  # success|partial|failure
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")

    steps: Mapped[list["MissionStep"]] = relationship(cascade="all, delete-orphan", order_by="MissionStep.order_index")
    agents: Mapped[list["AgentRun"]] = relationship(cascade="all, delete-orphan", order_by="AgentRun.order_index")
    findings: Mapped[list["Finding"]] = relationship(cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(cascade="all, delete-orphan")
    code_changes: Mapped[list["CodeChange"]] = relationship(cascade="all, delete-orphan", order_by="CodeChange.path")
    tests: Mapped[list["TestRun"]] = relationship(cascade="all, delete-orphan")
    security_findings: Mapped[list["SecurityFinding"]] = relationship(cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(cascade="all, delete-orphan")
    release_gates: Mapped[list["ReleaseGate"]] = relationship(cascade="all, delete-orphan", order_by="ReleaseGate.order_index")
    metrics: Mapped[list["Metric"]] = relationship(cascade="all, delete-orphan")
    audit: Mapped[list["AuditEvent"]] = relationship(cascade="all, delete-orphan", order_by="AuditEvent.at")

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status in ("completed", "skipped", "failed"))
        return round(done / len(self.steps), 2)


class MissionStep(Base):
    __tablename__ = "mission_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    stage: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    message: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    agent: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued")  # queued|running|completed|failed|blocked
    summary: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    findings_json: Mapped[list] = mapped_column(JSON, default=list)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    affected_files: Mapped[list] = mapped_column(JSON, default=list)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    agent: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(16), default="info")
    category: Mapped[str] = mapped_column(String(32), default="")
    file: Mapped[str] = mapped_column(String(255), default="")
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    agent: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))  # file|line|commit|test|scan|command|diff|review|metric|log
    label: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(255), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class CodeChange(Base):
    __tablename__ = "code_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    path: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="modified")  # added|modified|removed
    added: Mapped[int] = mapped_column(Integer, default=0)
    removed: Mapped[int] = mapped_column(Integer, default=0)
    diff: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    suite: Mapped[str] = mapped_column(String(64), default="unit")
    phase: Mapped[str] = mapped_column(String(32), default="investigate")  # investigate|validate|regression
    path: Mapped[str] = mapped_column(String(255), default="")
    name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="passed")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")


class SecurityFinding(Base):
    __tablename__ = "security_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    rule: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(255), default="")
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    remediation: Mapped[str] = mapped_column(Text, default="")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    reviewer: Mapped[str] = mapped_column(String(32), default="critic")
    verdict: Mapped[str] = mapped_column(String(32))  # pass|changes_requested
    score: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    issues_json: Mapped[list] = mapped_column(JSON, default=list)
    reviewed_files: Mapped[list] = mapped_column(JSON, default=list)


class ReleaseGate(Base):
    __tablename__ = "release_gates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pass|fail|pending
    detail: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overall: Mapped[str] = mapped_column(String(16), default="blocked")  # ready|blocked|in_progress


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(128), default="")
    value: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(16), default="")
    source: Mapped[str] = mapped_column(String(32), default="measured")
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"))
    agent: Mapped[str] = mapped_column(String(32), default="system")
    category: Mapped[str] = mapped_column(String(32), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RepositoryIndex(Base):
    __tablename__ = "repository_index"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    path: Mapped[str] = mapped_column(String(255))
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    files: Mapped[list] = mapped_column(JSON, default=list)
    tests: Mapped[list] = mapped_column(JSON, default=list)
    architecture: Mapped[dict] = mapped_column(JSON, default=dict)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)