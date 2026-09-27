# FORGE — IBM Bob 2.0 Hackathon Submission (lablab.ai)

**Project:** FORGE — the mission-driven code repair engine.

## Demo video
- **Loom:** https://www.loom.com/share/d17120f101934d8f86577c3ce9f9f8b0
- Covers: live app, "run a mission" flow, root cause → fix → verified-by-tests release gate.

## Where IBM Bob was used (evidence)
- **Bob task session summary** — [`bob-task-session-summary.html`](./bob-task-session-summary.html) (Bob IDE, org `bob-001 (us-east)`): Bob analyzed FORGE's mission pipeline and fixed the ForgeMart double-charge checkout race condition (compare-and-set lock, idempotent order creation, webhook ordering). Result: **20/20 tests pass**.
- **Bob session screenshots** — see [`bob-evidence/`](./bob-evidence/).
- **Live verification in FORGE** — FORGE reran and recorded the repaired ForgeMart suite end-to-end:
  - `mission-f788e610f8d3` — ForgeMart: 20/20 tests, critic 7/7, release pass.
  - `mission-c33d93ba3984` — ForgeMart: success, gate pass.
- **FORGE fixing itself** — while testing FORGE on a new Python bug, we found a limitation in FORGE's repair engine (it could not resolve Python `from x import ...` imports). FORGE's AI-fix path then repaired `bugdemo.py` (`return subtotal + tax * 2` → `return subtotal + tax`) with all tests verified green:
  - `mission-6915394a1579` — outcome success, gate pass, 5/5 tests.

## In this repo
| Path | What it proves |
|---|---|
| `SUBMISSION/bob-task-session-summary.html` | Bob 2.0 task session (race-condition fix, 20/20 tests) |
| `SUBMISSION/bob-evidence/` | Bob IDE screenshots |
| `backend/app/agents/repair.py` | FORGE's generative repair agent (improved during this hackathon) |
| `forgemart/` | Sample store whose checkout race defect FORGE repaired |