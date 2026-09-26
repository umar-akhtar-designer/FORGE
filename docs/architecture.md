# Architecture

```
                ┌──────────────────────────────┐
                │   Next.js 16 (frontend 3000)  │
                │  Command Center / Mission Ctl │
                └──────────────┬───────────────┘
                               │ REST /api/* (fetch, poll 1.2s)
                ┌──────────────▼───────────────┐
                │   FastAPI (backend 8000)      │  app/main.py, app/api/routes.py
                └──────────────┬───────────────┘
                               │ run_mission(mission_id, mission_text, demo_seed, repo)
                ┌──────────────▼───────────────┐
                │   Orchestrator                │  orchestration/pipeline.py
                │   10 steps · 8 agent runs     │
                └──────┬────────┬──────┬───────┘
                       │        │      │
      ┌────────────────▼─┐   ┌──▼────────────┐   ┌──────────────┐
      │ Repository Intel │   │ Agent engine  │   │ Evidence &   │
      │ intel/           │   │ agents/       │   │ Metrics      │
      │  indexer         │   │  architect    │   │ evidence.py  │
      │  workspace       │   │  debugger     │   │ metrics.py   │
      │                  │   │  security     │   │ report.py    │
      │                  │   │  tester       │   └──────────────┘
      │                  │   │  actor        │
      │                  │   │  critic       │
      │                  │   │  release      │
      └──────────────────┘   └───────────────┘
```

## Backend pipelines

`orchestration/pipeline.py` runs 10 steps sequentially; steps 4 (investigate)
and 7 (validate) fan out. Before any agent runs, the mission text is matched
against the **skill registry** (`app/skills/registry.py`) — the matched skill
(if any) feeds the plan, probes, fix, and regression test.

| # | Step | Agents | What is produced |
|---|---|---|---|
| 1 | init | — | workspace copy of the repo, dependency install, symlinked node_modules |
| 2 | index | — | file index, AST-ish architecture map, test discovery, dependency graph |
| 3 | plan | architect | mission plan + scope contract (≤3 files) |
| 4 | investigate | debugger, security, tester (parallel) | call chains, security scan, baseline test run (fails: 2 rows) |
| 5 | root_cause | debugger | synthesized root cause + candidates |
| 6 | implement | actor | applies the fix from the skill's remediation patches, computes diffs |
| 7 | validate | tester | regression + full suite re-run (passes: rows flip to passed) |
| 8 | critic | critic | review, verdict + score |
| 9 | release | release | 7-gate evaluation |
| 10 | report | — | evidence graph, metrics, audit trail, persisted report |

## Agent contract

Every agent returns a normalized `AgentRun` shape:

```
status, summary, result,
findings[] (agent, title, detail, severity, category, file, line, confidence, evidence_refs),
evidence[] (agent, kind, label, source, payload),
affected_files[], recommendations[], confidence, duration_ms
```

The API serializes persisted `AgentRun` rows so the frontend never joins data
across the wire — the payload it got back is the same shape the engine wrote.

## Skill registry

The engine itself is repository-agnostic. Everything ForgeMart-specific is data
declared in a **skill**: `app/skills/<skill-id>/` containing a `manifest.json`
plus patch and regression templates.

```
app/skills/checkout-race/
  manifest.json          id, keywords, detect.signals, orchestration, callers,
                         observations[] (probe kind + file + regexes + title),
                         remediation.patches[], regression.{dest,template,entry_points}
  patches/checkout.ts    the corrected checkout.ts (blob → diff vs workspace)
  patches/orders.ts      the corrected orders.ts
  regression/checkout.race.test.ts   the vitest regression template (deterministic)
```

- **Matching**: a skill matches when its `detect.signals` appear in the mission
  text; the pipeline seeds nothing else into the agents.
- **Probing** (`run_observations`): generic probe kinds — `missing_guard_in_method`
  (e.g. an `async create()` lacking an idempotency guard), `line_before`,
  `presence` — emit observations with real `file:@line` evidence refs.
- **Remediation**: `actor` copies the skill's patches into the workspace, then
  recomputes the diff against the private workspace copy — the fix is never an
  invented string.
- **Regression**: `tester` writes the skill's template only when the workspace
  has no matching regression file; the same `vitest run` is red pre-fix and
  green post-fix.
- A mission on a repository with **no** matched skill still indexes, plans,
  investigates, tests and gates — it simply applies no fix.

## Release gate (7 checks)

`build` (tsc in the workspace), `unit_tests`, `regression`, `security` (0
critical), `code_review` (critic verdict pass), `architecture` (every changed
component is inside the skill's declared scope — integrity check), `scope`
(files changed ≤ 3). Overall gate = all pass → `ready`.

Checks are tri-state. A check that **cannot honestly run** is `na` (not
applicable) rather than a fake pass: no tsc installed → `build` `na`; no
supported test runner (vitest/jest/pytest) → `unit_tests` (and jobs that depend
on it) `na`; no skill-generated regression → `regression` `na`; no changes →
`architecture` and `scope` `na`. `na` never blocks a release, but is always
visible in the report so nothing is fabricated.

## Bring Your Own Software (BYOS)

Users can point FORGE at their own repository instead of the bundled demo:

- `POST /api/repositories/upload` accepts a `.zip` (≤60 MB, ≤3000 entries,
  ≤400 MB uncompressed). Members are validated before extraction — absolute
  paths, `..` traversal and symlinks are rejected, Darwin artifacts skipped —
  and no code in the archive is ever executed.
- The upload is extracted under `config.UPLOADS_DIR`, the project root detected
  (single top-level folder is unwrapped), indexed via the same
  `index_directory` path as the demo, and registered with `store` so
  `GET /api/repositories` and the launch form's repository selector pick it up.
- The pipeline resolves the repo root from the uploaded index
  (`store.get_repository_index`) with `forgemart/` as the fallback; the
  workspace is a private copy of the uploaded source (vitest runs only when the
  archive ships its own `node_modules`).
- Test execution is runner-discovered (`detect_runner` — vitest, jest or
  pytest) so an uploaded repo is tested in its own toolchain or honestly marked
  not-executed. Uploaded repos without a matching skill complete the incident
  with a real scan, a review verdict ("no patch to review"), and `na` gates —
  never an invented fix or metric.

## Generative repair (optional LLM layer)

When **no skill matches** and no deterministic fix exists, FORGE can ask an
LLM to propose a real fix — as a *proposal*, never a blind patch:

1. `repair` agent gathers FORGE's real evidence (root-cause candidates, the
   failing-test rows, and the current contents of the test's import
   neighbors + debugger-affected files) and asks the model for whole-file
   edits in a strict JSON schema.
2. The proposal is written to the mission workspace and then **verified by the
   real validation suite + typecheck**. Only a green run is committed, with
   its real diff and reason `AI repair (LLM-generated) verified by validation`.
   Anything that fails validation is reverted and reported honestly.
3. Any OpenAI-compatible endpoint works: default is anonymous Pollinations
   (no key); set `FORGE_LLM_BASE_URL`/`FORGE_LLM_API_KEY`/`FORGE_LLM_MODEL` to
   switch to Groq/OpenRouter/Gemini/Mistral etc.

Determinism is preserved: the layer is **off by default**
(`FORGE_LLM_ENABLED=true` to enable). When it is off, the no-skill path is
exactly as described above — `na` gates, no invented fix or metric.

## GitHub pull requests (optional)

A verified fix can be shipped: set `GITHUB_TOKEN` and `GITHUB_REPO`
(`owner/name`) and the mission page shows **Open GitHub PR**. `create_pr`
creates a per-mission branch on the repo's default branch, writes exactly the
committed files via the contents API (reconstructed from the workspace copy or
pristine + stored diff), and opens a PR whose body carries the mission, root
cause and release-gate summary. Only changes the pipeline actually committed
and verified are pushed. Off until a token is configured; disabled missions
show the configure hint rather than a fake button.

## Learn: verified fixes become playbooks

After each mission, `app/skills/learn.py` turns any **AI-verified** fix into a
new skill:

1. The stored diff's removed ("buggy") lines are used as a *detection signal*,
   keyed by a stable hash (`learned-<sha>`) so the same defect is never
   duplicated.
2. The playbook reuses the skills engine end-to-end: presence probe → debugger
   → actor patch → regression/validation. A real `manifest.json` + the fixed
   file as a patch template are written to `config.SKILLS_DIR` and are fully
   human-reviewable.
3. The next time the same buggy pattern appears, FORGE fixes it
   deterministically without any LLM call. `FORGE_SKILL_LEARNING` gates the
   feature (default on). Author-written skills (e.g. `checkout-race`) and
   learned skills are both returned by `load_all()`.

## Test runners: multi-language honesty

`tester.detect_runner` detects a real, installed runner before ever claiming
tests ran:

- **Node**: vitest/jest binaries must exist under `node_modules/.bin`.
- **Python**: requires `requirements.txt`/pytest config (pytest runs through
  `python3 -m pytest`).
- **Go**: `go.mod` + `go` on PATH → `go test -json -v ./...`, parsed from the
  event stream (`app/agents/tester._parse_go_events`).
- **Rust**: `Cargo.toml` + `cargo` on PATH → `cargo test`, parsed from the
  harness output.

No runner / no toolchain ⇒ the gate is `na` with an explicit reason — FORGE
never invents results.

## Security model

- **Uploads**: zip members validated before extraction (no absolute paths,
  no `..` traversal, no symlinks, zip-bomb caps on entries/size), extracted
  into a private per-upload dir. Code is never executed at that stage.
- **Workspaces**: each mission gets a private copy; the pristine repo is never
  mutated.
- **API**: optional bearer token (`FORGE_API_TOKEN`) gates every write route
  (missions, upload, connect, PR); read routes stay open. A sliding-window
  rate limit (default 60 req/min/client) protects all routes.
- **LLM providers**: requests carry `Authorization: Bearer` only when a key is
  configured; no provider secrets are ever logged or returned via the API.
- **GitHub**: the token is sent only to `api.github.com` / `codeload.github.com`
  and is never stored — it lives in process env.

## Deployment

`backend/Dockerfile`, `frontend/Dockerfile` and `docker-compose.yml` ship a
single-command deployment (`docker compose up --build`). The backend persists
DB + uploads + workspaces on a named volume; `FORGEMART_DIR` is baked into the
image so the demo works out of the box. See `.env.example` for every knob and
`README` for the full configuration reference.

## Determinism

- `mission_text` + `seed` → the exact same mission, steps, findings and
  metrics every run.
- The pristine `forgemart/` is never mutated; each mission gets a private
  workspace copy under `config.WORKSPACES_DIR` (node_modules symlinked).
- Regression is a real `vitest run` and is red before `actor`, green after.

## Headless engine

The engine imports without a running server — `orchestration/pipeline.run_mission`
is called directly by `pytest` (see `backend/tests/test_pipeline.py`), which is
how the whole loop is regression-tested in ~40–58s offline.