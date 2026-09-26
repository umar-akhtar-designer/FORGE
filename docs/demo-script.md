# Demo script

10-minute, fully deterministic run. Numbers below are from a verified
end-to-end execution of the default mission on a pristine checkout of the
repo (same every time, no LLM calls).

## 0. Pre-flight (~1 min)

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --port 8000          # terminal 1
cd frontend && npm run dev                 # terminal 2
open http://localhost:3000
```

## 1. Command Center (landing page ~1 min)

- Title line: *"An autonomous engineering control plane that turns one mission
  into proof."*
- Pipeline chip strip: INIT → INDEX → PLAN → INVESTIGATE → ROOT-CAUSE →
  IMPLEMENT → VALIDATE → CRITIC → RELEASE.
- Launch card is pre-filled: *"Investigate a race condition in the checkout
  flow where a second confirm can fail or duplicate the order."*
- Stat strip reflects the real indexed repo (43 files, 8 tests discovered).

> **Talking point:** every number on this page is read live from the backend
> (`/api/health`, `/api/repositories`, `/api/missions`) — nothing is static.

## 2. Live run (~1 min)

Press **Launch Mission**. Mission Control opens on a client page that polls
`/api/missions/{id}` every 1.2 s while it runs.

- Progress bar climbs; agent strip fills left-to-right with per-agent durations.
- Full loop completes in **~3–6 s**.

> Actually measured durations (one representative run):
> security ~2.8 s · tester ~2.9 s · debugger ~40 ms · others <5 ms.
> The run is driven by the **skill registry**: the checkout-race skill matches
> the mission text and supplies the probes, fix patches and regression template —
> the engine itself is repository-agnostic.

## 3. Root Cause tab

- Root-cause hypothesis: **"Order creation is not idempotent for a session"**
  with confidence %, file/line reference, and the finding agent.
- Call chain from the debugger (webhook confirm → `completeCheckout` →
  `orders.create` → `PAYMENT_NOT_LOCKED`).

## 4. Actor / Critic tab

- Two diffs, real unified output with +N/−N: `packages/database/src/orders.ts`
  (+8/−5, sessionId idempotency) and `packages/payments/src/checkout.ts`
  (+19/−12, lock held until confirm).
- Critic verdict **pass · 100%** over the changes.

## 5. Tests tab (the money shot)

- **Investigate phase** — 18 unit tests pass, plus the regression suite that
  is **red: 2 failed** (the bug reproduced on the pristine workspace).
- **Validate phase** — the same 2 regression rows are now **green: 2 passed**,
  full suite 20 rows + typecheck row.

> Flip the phase toggle on the demo: before → red, after → green. Same test
> file, real `vitest run`, no mock.

## 6. Security tab

- Scan counts: critical 0 · high 1 · low 1 (8 rules × 31 files, real execution).
- High: webhook endpoint does not verify the provider signature
  (`apps/api/src/webhooks/payment.ts`).
- Low: server/version header disclosure (`apps/api/src/http.ts`).
- Each entry shows rule, remediation, file:line. Failed/risky checks are
  visible, never hidden.

## 7. Release Gate tab

- **7/7 checks pass** → overall **READY**: build, unit_tests, regression,
  security (0 critical), code_review, architecture (changes confined to the
  skill's declared components — integrity OK), scope (2 files ≤ 3).
- The Skills card shows the matched **checkout-race** skill with its probes and
  patch paths.

## 8. Evidence Graph + Report + Activity

- 9-node live graph; every node/edge from persisted report rows.
- Report metrics, all tagged: measured workflow **~5.2 s** vs 8 agents, 41
  tests executed, 2 tests generated, 1 skill matched, repo stats (43 files,
  2.7 k lines, 8 tests, 8 components).
- Manual-workflow baseline **36 min** is explicitly labeled *estimate (docs,
  not measured)* — the only estimate in the whole product.
- Activity tab is the audit trail: 18 agent events with timestamps, including
  the skill-match event (`audit.category == "matched"`).

## Integrity notes

- The pristine demo repo stays buggy; fixes live in skill patch templates
  (`backend/app/skills/checkout-race/patches/*.ts`), applied only in each
  mission's private workspace.
- Backend test suite: `cd backend && pytest` → **24/24 green** (12 pipeline +
  API + 5 skill-registry + 7 BYOS) in ~70 s, exercising the real headless engine.
- Frontend: `npx tsc --noEmit && npm run build` → clean, 3 routes.
- New repositories with no matching skill run the full loop (index → plan →
  investigate → gates) and apply no fix — the engine stays honest about what
  it does not know.
- **Bring Your Own Software (BYOS):** upload any `.zip` from the launch screen
  (`POST /api/repositories/upload`) → it is extracted safely (traversal /
  symlink / size guards, no code execution), indexed, and added to the Target
  repository selector. Missions against an upload complete incident with
  `na`-marked gates whenever a check cannot honestly run (no tsc → build `na`,
  no supported runner → unit_tests `na`, no matching skill → regression `na`,
  no changes → architecture/scope `na`). Release is `ready` only when every
  applicable check passes; nothing is fabricated.
- BYOS demo (live-verified): upload `storefront.zip` (3 Python files, no
  runner) → mission completes `success` with **0 changes**, gate `ready`,
  checks `[build na, unit_tests na, regression na, security pass, code_review
  pass, architecture na, scope na]`, skills `[checkout-race matched=False]`.