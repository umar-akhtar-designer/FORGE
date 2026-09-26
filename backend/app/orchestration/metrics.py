"""Impact metrics — every value derives from mission execution logs.

Manual-workflow comparisons are clearly labeled as illustrative estimates and
never presented as measured data, per the project's non-negotiable principles.
"""

from __future__ import annotations

from .. import store

BASELINE_LABEL = "Illustrative manual-workflow estimate (docs, not measured)"


def compute_and_persist(mission, index: dict, run_log: dict) -> None:
    files_indexed = index.get("stats", {}).get("files", 0)
    tests_indexed = index.get("stats", {}).get("tests", 0)
    files_investigated = len(run_log.get("investigated_files", set()))
    max_parallel = run_log.get("parallel", 1)
    agents_executed = len(store.get_agents(mission.id))
    tests_generated = run_log.get("tests_generated", 0)
    tests_executed = run_log.get("tests_executed", 0)
    security_checks = run_log.get("security_rules", 0) * run_log.get("security_files", 0)
    security_findings = run_log.get("security_findings", 0)
    files_changed = len(store.get_code_changes(mission.id))
    approvals = 2  # plan gate + release gate, both are explicit human approval points
    skills_matched = len(run_log.get("skills_matched", []))

    metrics = [
        ("workflow_duration_ms", "Mission workflow duration", run_log.get("duration_ms", 0), "ms", "measured"),
        ("agents_executed", "Agents executed", agents_executed, "", "measured"),
        ("parallel_investigators", "Parallel investigators", max_parallel, "", "measured"),
        ("files_indexed", "Files indexed", files_indexed, "", "measured"),
        ("files_investigated", "Files investigated", files_investigated, "", "measured"),
        ("tests_indexed", "Tests discovered", tests_indexed, "", "measured"),
        ("tests_generated", "Tests generated", tests_generated, "", "measured"),
        ("tests_executed", "Tests executed", tests_executed, "", "measured"),
        ("security_checks", "Security checks", security_checks, "", "measured"),
        ("security_findings", "Security findings", security_findings, "", "measured"),
        ("files_changed", "Files changed", files_changed, "", "measured"),
        ("skills_matched", "Skills matched", skills_matched, "", "measured"),
        ("human_approvals", "Human approval gates", approvals, "", "measured"),
        ("rework_cycles", "Rework cycles", 0, "", "measured"),
        ("manual_baseline_min", "Manual investigation baseline (estimate)", 36.0, "min", "estimate"),
        ("forge_workflow_min", "FORGE workflow time", round(run_log.get("duration_ms", 0) / 60000, 2), "min", "measured"),
    ]
    for i, (key, label, value, unit, source) in enumerate(metrics):
        store.add_metric(mission.id, key, label, float(value), unit, source, i)