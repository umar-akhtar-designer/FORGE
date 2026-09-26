# FORGE — Autonomous Engineering Control Plane

A developer gives FORGE one engineering mission. FORGE turns it into an
observable, evidence-driven workflow that actually ships a fix:

```
MISSION → REPOSITORY INTELLIGENCE → PLAN → PARALLEL AGENTS
→ ROOT CAUSE → IMPLEMENTATION → TESTS → SECURITY
→ ACTOR/CRITIC → RELEASE GATE → EVIDENCE REPORT → LEARN → PR
```

Built with FastAPI + SQLAlchemy (backend) and Next.js 16 + framer-motion
(frontend).

## Why this exists

Most "autonomous engineer" demos fake the output. FORGE is built on four
non-negotiables:

1. **Evidence over claims.** Every finding references real files, lines,
   tests, scans or diffs. Nothing is invented.
2. **Real execution over fake animation.** Agents parse the repository, run
   tests, compute diffs, scan for security issues and evaluate gates. The
   graph you see is drawn from persisted DB rows, not scripted scenes.
3. **Deterministic when it should be.** The same mission on the same
   repository replays identically. The generative AI fix layer is **off by
   default**; when it is on, nothing is ever committed unless the real
   validation suite + typecheck pass.
4. **No fabricated metrics.** Impact numbers come straight from execution
   logs and are tagged `source: measured` or `source: estimate`.

## What it does now — the full product loop

1. **Bring your own software.** Upload a `.zip`, or paste a **GitHub URL**
   (`octo/widgets`, `https://github.com/octo/widgets/tree/dev`) to connect a
   real repository. Archives are extracted safely — no code executed. GitHub
   connect works for any public repo and for private repos when
   `GITHUB_TOKEN` is configured.
2. **Investigate.** The engine indexes the repo (components, dependencies,
   tests) and runs agents in parallel. A matching **skill** declares probes,
   fix patches and a deterministic regression test.
3. **Fix.**
   - *Skill matched* → FORGE applies its author-written playbook patch.
   - *No skill, generative layer on* → FORGE asks the LLM for a fix against
     the **real failing tests and root-cause evidence**, then **re-runs the
     real suite + typecheck** on the workspace copy. A green result is
     committed; anything unverified is **reverted and reported** honestly.
   - Test runners are detected for real: **vitest, jest, pytest, Go
     (`go test`), Cargo (`cargo test`)** — none installed means the gate is
     marked `na`, never a fabricated pass.
4. **Validate & release-gate.** Full suite, typecheck, security scan
   (`ruff`/pattern rules), code review, architecture, scope. Any failed check
   is shown, never hidden.
5. **Ship.** One click opens a real **GitHub pull request** with the mission,
   root cause and gate summary.
6. **Learn.** Every fix FORGE ships with AI becomes a **learned skill** — a
   reviewable playbook (`backend/app/skills/learned-*`). The next time FORGE
   sees the same buggy pattern it fixes it deterministically, **no LLM
   required**. FORGE grows its own brain from real, verified work.

## Repository layout

| Path | Role |
|---|---|
| `backend/` | FastAPI + SQLAlchemy engine. Intelligence, agents, orchestrator, release gate, metrics, REST API. |
| `frontend/` | Next.js command-center UI (Command Center + Mission Control). |
| `forgemart/` | Demo e-commerce monorepo with a deliberately injected checkout race-condition defect. |
| `docs/` | Design notes — architecture, evidence model, demo script. |

## Quickstart — local

```bash
# backend (port 8000)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# with the generative fix layer + OpenRouter (see .env.example):
FORGE_LLM_ENABLED=true \
FORGE_LLM_BASE_URL=https://openrouter.ai/api/v1 \
FORGE_LLM_API_KEY=sk-or-v1-... \
FORGE_LLM_MODEL=cohere/north-mini-code:free \
uvicorn app.main:app --port 8000

# frontend (port 3000)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The built-in demo (`forgemart`, a checkout
race-condition defect) is wired and ready — just hit **Launch mission**. See
`docs/demo-script.md` for the exact talking points and numbers.

## Docker deployment

```bash
cp .env.example .env      # fill in FORGE_API_TOKEN / LLM / GitHub values
docker compose up --build
```

- Backend: http://localhost:8000 (data persists in the `forge-data` volume)
- Frontend: http://localhost:3000

## Configuration reference

Set via environment variables (all optional except where noted):

### Core
| Variable | Default | Meaning |
|---|---|---|
| `FORGE_DB_URL` | `sqlite:///backend/data/forge.db` | Database connection. |
| `FORGE_UPLOADS_DIR` / `FORGE_WORKSPACES_DIR` | under `backend/data` | Archive + worker-workspace locations. |
| `FORGE_SKILLS_DIR` | `backend/app/skills` | Where author + learned skills live. |
| `FORGEMART_DIR` | `forgemart/` | Path to the bundled demo repo. |
| `FORGE_API_TOKEN` | *(unset)* | When set, every write endpoint requires `Authorization: Bearer <token>` (or `X-API-Key`). |
| `FORGE_API_RATE_LIMIT` | `60` | Requests per minute per client (IP, or token when auth is on). |

### Generative repair
| Variable | Default | Meaning |
|---|---|---|
| `FORGE_LLM_ENABLED` | `false` | Turn on the AI repair layer. |
| `FORGE_LLM_BASE_URL` | `https://text.pollinations.ai/openai` | Any OpenAI-compatible endpoint. |
| `FORGE_LLM_API_KEY` | *(empty)* | Bearer key for the provider. |
| `FORGE_LLM_MODEL` | `openai` | e.g. `cohere/north-mini-code:free` on OpenRouter. |
| `FORGE_LLM_FALLBACK_URL` / `FORGE_LLM_FALLBACK_MODEL` | Pollinations `openai` | Automatic keyless fallback if the primary provider fails. |
| `FORGE_LLM_TIMEOUT_S` | `90` | Request timeout. |
| `FORGE_LLM_MAX_FILES` / `FORGE_LLM_MAX_FILE_BYTES` | `3` / `80000` | Context budget per repair. |

### Learning
| Variable | Default | Meaning |
|---|---|---|
| `FORGE_SKILL_LEARNING` | `true` | Record verified AI fixes as reusable skills. |

### GitHub PR
| Variable | Default | Meaning |
|---|---|---|
| `GITHUB_TOKEN` | *(empty)* | GitHub token with `repo` scope. Enables PRs (+ private repo connects). |
| `GITHUB_REPO` | *(empty)* | `owner/name` of the target repo for PRs. |
| `GITHUB_DEFAULT_BRANCH` | `main` | Base branch for PRs and connects. |

## API summary

All routes are under `/api` and rate-limited. With `FORGE_API_TOKEN` set,
`POST /missions`, `POST /repositories/upload`, `POST /repositories/connect`
and `POST /missions/{id}/pr` require the bearer token. Read endpoints stay
open:

| Route | Purpose |
|---|---|
| `GET /health` | Liveness. |
| `POST /missions` | Launch a mission against a registered repo. |
| `GET /missions` · `GET /missions/{id}` · `/report` · `/impact` · `/activity` · `/release-gate` | Mission state + evidence. |
| `GET /repositories` · `POST /repositories/upload` · `POST /repositories/connect` | Repos in the engine. |
| `GET /skills` | Author + learned skills. |
| `GET /github/status` | PR integration state. |
| `POST /missions/{id}/pr` | Open a real GitHub PR for a verified fix. |

## Verification

```bash
cd backend && source .venv/bin/activate && pytest        # full suite green
cd frontend && npx tsc --noEmit && npm run build         # clean
docker compose config                                    # compose file valid
```