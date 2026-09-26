# FORGE — Autonomous Engineering Control Plane

## Mission

A developer gives FORGE one engineering mission. FORGE transforms it into an
observable, evidence-driven engineering workflow:

```
MISSION → REPOSITORY INTELLIGENCE → PLAN → PARALLEL AGENT INVESTIGATION
→ ROOT CAUSE → IMPLEMENTATION → TESTING → SECURITY REVIEW
→ ACTOR/CRITIC REVIEW → RELEASE GATE → EVIDENCE REPORT
```

## Non-negotiable principles

- **Evidence over claims.** Every finding references real files, lines, tests,
  scans or diffs. No invented facts.
- **Real execution over fake animation.** Agents actually parse code, run tests,
  compute diffs and evaluate gates. Nothing is fabricated.
- **Deterministic demo.** The same mission on the same repository replays
  identically and always works end-to-end without external LLMs.
- **Human approval gates are visible.** Failed checks are never hidden.
- **No fabricated metrics.** Impact numbers come from execution logs.

## Repo layout

| Path | Role |
|---|---|
| `backend/` | FastAPI + SQLAlchemy. Domain models, repository intelligence, 6 agents, orchestrator, release gate, metrics. |
| `frontend/` | Next.js 16 + TypeScript + Tailwind — the Obsidian Forge command center UI. |
| `forgemart/` | Demo e-commerce repository with a deliberately injected checkout race-condition defect. |
| `docs/` | Design notes: architecture, evidence model, agent contracts. |

## How to run

Backend (port 8000):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend (port 3000):

```bash
cd frontend
npm install
npm run dev
```

## Engineering conventions

- Backend: Plain functions get injected dependencies; never construct global
  singletons inside engine modules. The engine must be importable headlessly.
- Every agent returns structured `AgentRun` output (status, summary, findings,
  evidence, affected files, recommendations, confidence, execution time).
- Frontend pages are client components that talk to `lib/api.ts`; the API base
  URL comes from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- Obsidian Forge theme tokens live in `frontend/app/globals.css` — do not
  introduce new ad-hoc colors.
- Before claiming a feature is complete: run `pytest` in backend and
  `npx tsc --noEmit && npm run lint && npm run build` in frontend.