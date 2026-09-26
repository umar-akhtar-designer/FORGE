"""Pydantic contracts for the FORGE API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]
AgentStatus = Literal["idle", "queued", "running", "completed", "failed", "blocked"]
MissionStatus = Literal["queued", "running", "completed", "failed", "blocked"]
Outcome = Literal["success", "partial", "failure"]


class MissionCreate(BaseModel):
    title: str = Field(default="", description="Short mission title")
    mission_text: str
    repository: str = "forgemart"
    seed: int = 0


class RepositoryFile(BaseModel):
    path: str
    name: str
    language: str
    type: str
    lines: int
    size: int
    imports: list[str] = []


class ArchitectureNode(BaseModel):
    id: str
    name: str
    kind: str
    files: int
    risk: int
    lead_file: str = ""


class ArchitectureEdge(BaseModel):
    source: str
    target: str
    weight: int = 0


class DependencyEntry(BaseModel):
    path: str
    name: str
    dependencies: dict[str, str] = {}


class RepositoryIndexOut(BaseModel):
    name: str
    path: str
    stats: dict[str, Any]
    files: list[RepositoryFile]
    tests: list[RepositoryFile]
    architecture: dict[str, Any]
    dependencies: list[DependencyEntry]
    source: dict[str, Any] | None = None


class Finding(BaseModel):
    id: int | None = None
    agent: str
    title: str
    detail: str = ""
    severity: Severity = "info"
    category: str = ""
    file: str = ""
    line: int | None = None
    confidence: float = 0.0
    evidence_refs: list[str] = []


class Evidence(BaseModel):
    id: int | None = None
    agent: str
    kind: str
    label: str = ""
    source: str = ""
    payload: dict[str, Any] = {}


class CodeChange(BaseModel):
    id: int | None = None
    path: str
    status: str
    added: int
    removed: int
    diff: str = ""
    reason: str = ""


class TestResult(BaseModel):
    id: int | None = None
    suite: str
    phase: str
    path: str
    name: str
    status: str
    duration_ms: int
    detail: str = ""


class SecurityFinding(BaseModel):
    id: int | None = None
    rule: str
    severity: Severity
    title: str
    path: str = ""
    line: int | None = None
    description: str = ""
    remediation: str = ""


class ReviewOut(BaseModel):
    id: int | None = None
    reviewer: str
    verdict: str
    score: float
    summary: str = ""
    issues: list[dict[str, Any]] = []
    reviewed_files: list[str] = []


class ReleaseGateOut(BaseModel):
    name: str
    status: str
    detail: str = ""
    order_index: int = 0
    checked_at: datetime | None = None


class ReleaseGateSummary(BaseModel):
    checks: list[ReleaseGateOut]
    overall: str


class MetricOut(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    source: str
    order_index: int = 0


class AuditEventOut(BaseModel):
    agent: str
    category: str
    message: str
    at: datetime


class AgentStep(BaseModel):
    stage: str
    name: str
    status: str
    message: str = ""
    order_index: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentRunOut(BaseModel):
    agent: str
    role: str = ""
    status: AgentStatus
    summary: str = ""
    result: dict[str, Any] = {}
    findings: list[Finding] = []
    evidence: list[Evidence] = []
    affected_files: list[str] = []
    recommendations: list[str] = []
    confidence: float = 0.0
    duration_ms: int = 0
    order_index: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MissionSummary(BaseModel):
    id: str
    title: str
    repository: str
    status: MissionStatus
    outcome: Outcome | str
    progress: float
    summary: str = ""
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int = 0
    error: str = ""


class MissionDetail(MissionSummary):
    mission_text: str
    seed: int
    steps: list[AgentStep] = []
    agents: list[AgentRunOut] = []
    gate_overall: str = "in_progress"


class EvidenceGraphNode(BaseModel):
    id: str
    label: str
    kind: str
    status: str
    count: int = 0
    detail: str = ""


class EvidenceGraphEdge(BaseModel):
    source: str
    target: str
    kind: str = "flow"


class EvidenceGraph(BaseModel):
    nodes: list[EvidenceGraphNode]
    edges: list[EvidenceGraphEdge]


class SkillOut(BaseModel):
    id: str
    name: str
    description: str = ""
    keywords: list[str] = []
    detect_signals: int = 0
    observations: int = 0
    patches: list[str] = []
    regression_dest: str = ""
    matched: bool = False


class MissionReport(BaseModel):
    mission: MissionSummary
    summary: str
    repository: RepositoryIndexOut
    root_cause: Finding | None = None
    planning: list[Finding] = []
    findings: list[Finding]
    evidence: list[Evidence]
    code_changes: list[CodeChange]
    tests: list[TestResult]
    security: list[SecurityFinding]
    security_scan: dict[str, int]
    reviews: list[ReviewOut]
    release_gate: ReleaseGateSummary
    metrics: list[MetricOut]
    activity: list[AuditEventOut]
    evidence_graph: EvidenceGraph
    skills: list[SkillOut] = []
    workflow_time_ms: int = 0
    baseline_minutes: int = 0


class ImpactMetric(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    source: str
    highlight: bool = False


class ImpactOut(BaseModel):
    metrics: list[ImpactMetric]
    baseline_label: str
    forge_duration_ms: int


class ActivityOut(BaseModel):
    events: list[AuditEventOut]


class LaunchResult(BaseModel):
    mission_id: str
    status: str = "queued"


class HealthOut(BaseModel):
    status: str
    service: str = "FORGE"
    version: str
    uptime_s: float


class SourcesOut(BaseModel):
    name: str
    organization: str
    purpose: str
    source_url: str
    usage: str