"""FORGE API routes."""

from __future__ import annotations

import threading
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .. import config, store
from ..intel import upload as upload_agent
from .security import rate_limit, require_token
from ..models import (
    ActivityOut,
    AuditEventOut,
    EvidenceGraph,
    HealthOut,
    ImpactMetric,
    ImpactOut,
    LaunchResult,
    MissionCreate,
    MissionDetail,
    MissionReport,
    MissionSummary,
    ReleaseGateSummary,
    RepositoryIndexOut,
    SkillOut,
    SourcesOut,
)
from ..orchestration import pipeline, report
from ..orchestration.evidence import gate_status
from ..skills import load_all

router = APIRouter(prefix="/api", dependencies=[Depends(rate_limit)])

STARTED = time.time()

SOURCES = [
    {
        "name": "ForgeMart",
        "organization": "Hackathon demo monorepo",
        "purpose": "Deployable e-commerce shop crafted for this submission.",
        "source_url": "https://github.com/notion-claude/forge-hack-2025",
        "usage": "Target repository analyzed and repaired end-to-end by FORGE.",
    },
]


def _mission_meta(m) -> dict:
    gates = store.get_gates(m.id)
    steps = store.get_steps(m.id)
    total = len(steps)
    done = sum(1 for s in steps if s.status in ("completed", "skipped", "failed"))
    progress = round(done / total, 2) if total else 0.0
    return {
        "id": m.id, "title": m.title, "repository": m.repository, "status": m.status,
        "outcome": m.outcome, "progress": progress, "summary": m.summary,
        "created_at": m.created_at, "started_at": m.started_at, "completed_at": m.completed_at,
        "duration_ms": m.duration_ms, "error": m.error,
        "mission_text": getattr(m, "mission_text", ""),
        "seed": int(getattr(m, "seed", 0) or 0),
        "steps": [
            {"stage": s.stage, "name": s.name, "status": s.status, "message": s.message,
             "order_index": s.order_index, "started_at": s.started_at, "completed_at": s.completed_at}
            for s in steps
        ],
        "agents": [
            {"agent": a.agent, "role": a.role, "status": a.status, "summary": a.summary,
             "result": a.result_json, "findings": a.findings_json, "evidence": a.evidence_json,
             "affected_files": a.affected_files, "recommendations": a.recommendations,
             "confidence": a.confidence, "duration_ms": a.duration_ms, "order_index": a.order_index,
             "started_at": a.started_at, "completed_at": a.completed_at}
            for a in store.get_agents(m.id)
        ],
        "gate_overall": gate_status(gates[0].overall) if gates else "in_progress",
    }


@router.get("/health", response_model=HealthOut, tags=["system"])
def health() -> dict:
    return {"status": "ok", "service": config.APP_NAME, "version": "1.0.0", "uptime_s": round(time.time() - STARTED, 1)}


def _available_repos() -> set[str]:
    names = {r.name for r in store.list_repository_indexes()}
    return config.ALLOWED_REPOS | names


@router.post("/missions", response_model=LaunchResult, tags=["missions"], dependencies=[Depends(require_token)])
def create_mission(body: MissionCreate) -> dict:
    if body.repository not in _available_repos():
        raise HTTPException(status_code=400, detail=f"Repository '{body.repository}' is not available. Allowed: {sorted(_available_repos())}")
    if not body.title:
        body.title = "Investigate checkout race condition" if "checkout" in body.mission_text.lower() else "Engineering mission"

    mission_id = f"mission-{uuid.uuid4().hex[:12]}"
    seed = int(body.seed or int(uuid.uuid4().int % (2**31)))
    store.create_mission(mission_id, body.title, body.mission_text, body.repository, seed)
    threading.Thread(target=pipeline.run_mission, args=(mission_id, body.mission_text, seed, body.repository), daemon=True).start()
    return {"mission_id": mission_id, "status": "queued"}


@router.get("/missions", response_model=list[MissionSummary], tags=["missions"])
def list_missions(limit: int = 50) -> list[dict]:
    out = []
    for m in store.list_missions(limit):
        out.append(_mission_meta(m))
    return out


@router.get("/missions/{mission_id}", response_model=MissionDetail, tags=["missions"])
def mission_detail(mission_id: str) -> dict:
    m = store.get_mission(mission_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return _mission_meta(m)


@router.get("/missions/{mission_id}/report", response_model=MissionReport, tags=["missions"])
def mission_report(mission_id: str) -> dict:
    try:
        return report.build(mission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mission not found") from exc


@router.get("/missions/{mission_id}/impact", response_model=ImpactOut, tags=["missions"])
def mission_impact(mission_id: str) -> dict:
    m = store.get_mission(mission_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    metrics = store.get_metrics(mission_id)
    highlights = {"workflow_duration_ms", "tests_generated", "files_investigated", "human_approvals", "manual_baseline_min", "forge_workflow_min"}
    items = [{"key": x.key, "label": x.label, "value": x.value, "unit": x.unit, "source": x.source, "highlight": x.key in highlights} for x in metrics]
    return {"metrics": items, "baseline_label": "Illustrative manual-workflow estimate (docs, not measured)", "forge_duration_ms": m.duration_ms}


@router.get("/missions/{mission_id}/activity", response_model=ActivityOut, tags=["missions"])
def mission_activity(mission_id: str) -> dict:
    m = store.get_mission(mission_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return {"events": [{"agent": a.agent, "category": a.category, "message": a.message, "at": a.at} for a in store.get_audit(mission_id)]}


@router.get("/missions/{mission_id}/release-gate", response_model=ReleaseGateSummary, tags=["missions"])
def mission_release_gate(mission_id: str) -> dict:
    gates = store.get_gates(mission_id)
    return {
        "overall": gate_status(gates[0].overall) if gates else "in_progress",
        "checks": [{"name": g.name, "status": g.status, "detail": g.detail, "order_index": g.order_index, "checked_at": g.checked_at} for g in gates],
    }


@router.get("/evidence", tags=["evidence"])
def recent_evidence(limit: int = 40) -> list[dict]:
    rows = []
    for m in store.list_missions(50):
        for e in store.get_evidence(m.id):
            rows.append({"mission_id": m.id, "agent": e.agent, "kind": e.kind, "label": e.label, "source": e.source, "payload": e.payload})
    return rows[-limit:]


@router.get("/repositories", response_model=list[RepositoryIndexOut], tags=["repositories"])
def repositories() -> list[dict]:
    out = []
    for idx in store.list_repository_indexes():
        out.append({"name": idx.name, "path": idx.path, "stats": idx.stats, "files": idx.files, "tests": idx.tests, "architecture": idx.architecture, "dependencies": idx.dependencies})
    return out


@router.post("/repositories/upload", response_model=RepositoryIndexOut, tags=["repositories"], dependencies=[Depends(require_token)])
def upload_repository(file: UploadFile) -> dict:
    data = file.file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Archive exceeds {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    try:
        root, name = upload_agent.extract_upload(data, file.filename or "repo")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    idx = upload_agent.register_repository(root, name)
    return {"name": idx["name"], "path": idx["path"], "stats": idx["stats"], "files": idx["files"], "tests": idx["tests"], "architecture": idx["architecture"], "dependencies": idx["dependencies"]}


@router.post("/repositories/connect", response_model=RepositoryIndexOut, tags=["repositories"], dependencies=[Depends(require_token)])
def connect_repository(body: dict) -> dict:
    from ..intel import github_api
    url = body.get("url")
    if not url or not isinstance(url, str) or not url.strip():
        raise HTTPException(status_code=400, detail="Provide a GitHub repository URL")
    try:
        idx = github_api.connect_repository(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except github_api.GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"name": idx["name"], "path": idx["path"], "stats": idx["stats"], "files": idx["files"], "tests": idx["tests"], "architecture": idx["architecture"], "dependencies": idx["dependencies"], "source": idx.get("source")}


@router.get("/sources/registry", response_model=list[SourcesOut], tags=["sources"])
def sources() -> list[dict]:
    return SOURCES


@router.get("/skills", response_model=list[SkillOut], tags=["skills"])
def skills() -> list[dict]:
    return [s.public() for s in load_all()]


@router.get("/github/status", tags=["github"])
def github_status() -> dict:
    from ..intel import github_api

    return {"enabled": github_api.enabled(), "repository": config.GITHUB_REPO or None}


@router.post("/missions/{mission_id}/pr", tags=["github"], dependencies=[Depends(require_token)])
def open_pull_request(mission_id: str) -> dict:
    from ..intel import github_api

    if not github_api.enabled():
        raise HTTPException(status_code=400, detail="GitHub PR is not enabled (set GITHUB_TOKEN and GITHUB_REPO).")
    m = store.get_mission(mission_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if m.status != "completed":
        raise HTTPException(status_code=409, detail="Mission is not complete.")
    if not store.get_code_changes(mission_id):
        raise HTTPException(status_code=409, detail="Mission has no committed changes to push.")
    try:
        return github_api.create_pr(mission_id)
    except github_api.GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc