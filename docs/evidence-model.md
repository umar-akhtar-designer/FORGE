# Evidence model

Every claim FORGE makes is backed by a row in the database and surfaced in the
UI. There is no animated "intelligence" that did not actually run.

## Domains (backend/app)

| Table | Purpose | Mapped to API |
|---|---|---|
| `Mission` | one mission = one workspace run | `MissionDetail` |
| `MissionStep` | pipeline stage audit | `steps[]`, activity feed |
| `AgentRun` | 8 executed agents with structured output | `agents[]` |
| `Finding` | analysis findings (anti-patterns, root-cause evidence) | `findings[]` |
| `Evidence` | real artifacts: files read, tests run, scans, diffs | `evidence[]` |
| `CodeChange` | actor diff per file (+/-, full unified diff) | `code_changes[]` |
| `TestResult` | vitest JSON rows, grouped by phase | `tests[]` |
| `SecurityFinding` | rule-based scan hits | `security[]` + `security_scan` counts |
| `Review` | critic verdict + score | `reviews[]` |
| `ReleaseGate` | one row per gate check | `release_gate.checks[]` |
| `MetricsSnapshot` | execution-derived KPIs | `metrics[]` |
| `RepositoryIndex` | frozen intelligence snapshot | `repositories[]`, report repo block |
| Audit events (`category=skill`) | skill match recorded with matched skill id | `report.skills[]`, `GET /api/skills` |

`ReleaseGate.status` is tri-state: `pass`, `fail`, or `na`. Gates that cannot
honestly run on the target archive (no test runner → `unit_tests`; no tsc →
`build`; no matching skill → `regression`; no changes → `architecture`/`scope`)
are stored and rendered as `na` — always visible, never a fabricated pass.

## Evidence kinds recorded

`repository-map`, `architecture-map`, `dependency-graph`, `test-discovery`,
`security-scan`, `test-results`, `regression-suite`, `source-reference`,
`diff-computed`, `skill-match`, `call-graph`, `probe-observation`.

## Evidence graph (frontend)

`EvidenceGraph` renders the persisted graph: mission → evidence → root-cause →
plan → changes → {tests, security} → critic → release. Every node and edge is
read from `/api/missions/{id}/report`, so what renders is what actually
happened.

## Metrics tagging

`metrics.py` writes each KPI with a `source` field:

- `measured` — from execution logs (e.g. `workflow_duration_ms` ~5200ms, 8
  agents, 41 tests executed, 2 tests generated, 1 skill matched).
- `estimate` — only the manual-workflow baseline, explicitly documented and
  labeled in the UI as an illustrative estimate, never presented as measured.

## How the defect evidence works

1. `investigate` phase executes the regression suite (a skill-declared template
   written to the workspace) against the **buggy** workspace → 2 failed rows
   (proof the bug exists).
2. `actor` applies the skill's remediation patches to the workspace copy.
3. `validate` phase runs the same suite → same 2 rows now `passed` (proof the
   fix works), plus the full unit suite (~20 rows) and a typecheck row.

The flip from red to green is the single most legible evidence artifact in the
demo and it is produced by real `vitest run` executions.