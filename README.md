# FORGE — Autonomous Engineering Control Plane

A developer gives FORGE one engineering mission. FORGE turns it into an
observable, evidence-driven workflow — from repository intelligence through
parallel agent investigation, root-cause, implementation, testing, security
review, release gate, and an evidence report.

```
MISSION → REPOSITORY INTELLIGENCE → PLAN → PARALLEL AGENT INVESTIGATION
→ ROOT CAUSE → IMPLEMENTATION → TESTING → SECURITY REVIEW
→ ACTOR/CRITIC REVIEW → RELEASE GATE → EVIDENCE REPORT
```

## Key capabilities

- **Deterministic skill-driven repair** — a skill library + repository indexing
  derives root cause and applies verified patches deterministically (no LLM).
- **Generative repair (optional)** — any OpenAI-compatible provider (e.g.
  OpenRouter `:free` models) with an automatic keyless fallback; every AI fix
  is verified against the real validation suite before it is committed.
- **Auto-skill learning** — every AI fix that passes validation is distilled
  into a learned skill, so the recurring defect is later fixed deterministically
  without the LLM.
- **Multi-language runners** — vitest, jest, pytest, Go, and Cargo test suites
  are detected and executed; results feed the release gates honestly.
- **GitHub integration** — connect a repository by URL (public repos need no
  token), fix it, and open a real pull request with full evidence.
- **Security & robustness** — static scan for secrets/eval, optional API token
  auth + rate limiting, and a release gate that never hides failed checks.
- **No fabricated metrics** — every finding, test count, and gate outcome comes
  from real execution.

## Repository layout

| Path | Role |
|---|---|
| `backend/` | FastAPI + SQLAlchemy engine: 6 agents, orchestrator, release gate, skills, GitHub + LLM integrations, security. |
| `frontend/` | Next.js 16 + TypeScript + Tailwind — the Obsidian-Forge command center UI. |
| `docs/` | Product README, architecture, evidence model, demo script. |
| `forgemart/` | Demo e-commerce repository with a deliberately injected checkout race-condition defect. |

## Quickstart

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

Open http://localhost:3000, upload a repository, give FORGE a mission, and
watch the evidence-driven loop run. An example always-works mission against the
bundled `forgemart` demo is in `docs/demo-script.md`.

Docker deployment (backend + frontend + volume):

```bash
cp .env.example .env      # fill in values you want to enable
docker compose up -d --build
```

## Configuration

All settings are environment variables (see `.env.example`):

- `FORGE_API_TOKEN` / `FORGE_API_RATE_LIMIT` — optional auth + rate limiting.
- `FORGE_LLM_ENABLED`, `FORGE_LLM_BASE_URL`, `FORGE_LLM_API_KEY`,
  `FORGE_LLM_MODEL` and the `FORGE_LLM_FALLBACK_*` pair — generative repair.
- `FORGE_SKILL_LEARNING` — learn playbooks from verified AI fixes.
- `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_DEFAULT_BRANCH` — pull requests from
  fixed missions (token needs `repo` scope).
- `FORGE_SKILLS_DIR`, `FORGE_WORKSPACES_DIR`, `FORGE_DATA_DIR` — runtime paths.

## Verification

Backend: `pytest` (52 tests) — coverage includes the pipeline, skills, runners,
LLM fallback, GitHub connect/PR, security, and learning.
Frontend: `npx tsc --noEmit && npm run lint && npm run build` — clean.
Deployment: `docker compose config` — valid.