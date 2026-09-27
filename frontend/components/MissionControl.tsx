"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity as ActivityIcon,
  ArrowLeft,
  Bug,
  CheckCircle2,
  FileDiff,
  Fingerprint,
  Flame,
  FlaskConical,
  Gavel,
  Printer,
  ScrollText,
  ShieldCheck,
  Target,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentRun, Finding, MissionDetail, MissionReport } from "@/lib/types";
import { fmtMs, severityColor, statusColor } from "@/lib/format";
import { Pill, ProgressBar, SeverityPill, StatusPill } from "./Badge";
import EvidenceGraph from "./EvidenceGraph";
import { DiffView } from "./Diff";

type Tab = "root" | "findings" | "critic" | "tests" | "security" | "gate" | "report" | "activity";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "root", label: "Root cause", icon: <Target className="h-3.5 w-3.5" /> },
  { id: "findings", label: "Findings", icon: <Bug className="h-3.5 w-3.5" /> },
  { id: "critic", label: "Changes / Critic", icon: <FileDiff className="h-3.5 w-3.5" /> },
  { id: "tests", label: "Tests", icon: <FlaskConical className="h-3.5 w-3.5" /> },
  { id: "security", label: "Security", icon: <ShieldCheck className="h-3.5 w-3.5" /> },
  { id: "gate", label: "Release gate", icon: <Gavel className="h-3.5 w-3.5" /> },
  { id: "report", label: "Report", icon: <ScrollText className="h-3.5 w-3.5" /> },
  { id: "activity", label: "Activity", icon: <ActivityIcon className="h-3.5 w-3.5" /> },
];

function RootCausePanel({ mission, report }: { mission: MissionDetail | null; report: MissionReport | null }) {
  const dbg = mission?.agents.find((a) => a.agent === "debugger");
  const rc = report?.root_cause;
  const chain = (dbg?.result?.chain as { path?: string; line?: number; kind?: string }[]) ?? [];
  const candidates = (dbg?.result?.root_cause_candidates as { rank: number; title: string; confidence: number; component?: string; affected_files?: string[] }[]) ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="panel p-5 lg:col-span-2">
        <h3 className="panel-title">Root cause hypothesis</h3>
        {rc ? (
          <div className="mt-3">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-lg font-bold text-gray-900">{rc.title}</h4>
              <SeverityPill severity={rc.severity} />
            </div>
            <p className="mt-3 font-mono text-[12px] leading-relaxed text-gray-600">{rc.detail}</p>
            <div className="mt-4 flex flex-wrap items-center gap-4 text-[12px] text-gray-500">
              <span className="font-mono">confidence {(rc.confidence * 100).toFixed(0)}%</span>
              <span className="font-mono">{rc.file}{rc.line ? `:${rc.line}` : ""}</span>
              <span className="font-mono">found by {rc.agent}</span>
            </div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-gray-400">Root-cause analysis in progress…</p>
        )}
      </div>

      <div className="panel p-5">
        <h3 className="panel-title">Call chain</h3>
        <div className="mt-3 space-y-2">
          {chain.length === 0 && <p className="text-xs text-gray-400">Waiting for debugger…</p>}
          {chain.map((c, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="font-mono font-semibold text-[#4F46E5]">{i + 1}</span>
              <span className="truncate font-mono text-[11px] text-gray-600">{c.path}</span>
              {c.line ? <span className="font-mono text-[10px] text-gray-400">:{c.line}</span> : null}
            </div>
          ))}
        </div>
      </div>

      {candidates.length > 0 && (
        <div className="panel p-5 lg:col-span-3">
          <h3 className="panel-title">Candidates</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {candidates.map((c) => (
              <div key={c.rank} className="rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-4">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[11px] font-semibold text-[#4F46E5]">RANK #{c.rank}</span>
                  <span className="font-mono text-[11px] text-[#059669]">{(c.confidence * 100).toFixed(0)}%</span>
                </div>
                <p className="mt-1 text-sm font-medium text-gray-900">{c.title}</p>
                <p className="mt-1 font-mono text-[10px] text-gray-500">{c.component}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function FindingsPanel({ report }: { report: MissionReport | null }) {
  if (!report) return null;
  const ordered = [...report.findings].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    return (order[a.severity] ?? 5) - (order[b.severity] ?? 5);
  });
  return (
    <div className="space-y-3">
      {ordered.map((f, i) => (
        <div key={i} className="panel p-4">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityPill severity={f.severity} />
            <span className="font-mono text-[10px] text-gray-500">{f.category}</span>
            <span className="ml-auto font-mono text-[10px] text-gray-500">{f.agent}</span>
          </div>
          <h4 className="mt-2 text-sm font-semibold text-gray-900">{f.title}</h4>
          <p className="mt-1 text-[12px] leading-relaxed text-gray-600">{f.detail}</p>
          {(f.file || f.line) && (
            <p className="mt-2 font-mono text-[10px] text-gray-500">
              {f.file}{f.line ? `:${f.line}` : ""} · {Math.round(f.confidence * 100)}% confidence
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function CriticPanel({ report, oid }: { report: MissionReport | null; oid: string }) {
  const [gh, setGh] = useState<{ enabled: boolean } | null>(null);
  const [prUrl, setPrUrl] = useState<string>("");
  const [prErr, setPrErr] = useState<string>("");
  const [loadingPr, setLoadingPr] = useState(false);

  useEffect(() => {
    let stopped = false;
    api.githubStatus().then((s) => !stopped && setGh(s)).catch(() => !stopped && setGh({ enabled: false }));
    return () => { stopped = true; };
  }, []);

  const openPr = async () => {
    setLoadingPr(true); setPrErr("");
    try {
      const res = await api.openPr(oid);
      setPrUrl(res.url);
    } catch (e) {
      setPrErr((e as Error).message);
    } finally {
      setLoadingPr(false);
    }
  };

  if (!report) return null;
  const review = report.reviews[0];
  const hasChanges = report.code_changes.length > 0;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        {report.code_changes.map((c) => {
          return (
            <div key={c.path} className="panel p-5">
              <div className="flex items-center justify-between gap-2">
                <h4 className="font-mono text-[12px] font-semibold text-gray-900">{c.path}</h4>
                <div className="flex gap-2">
                  <span className="font-mono text-[10px] text-[#059669]">+{c.added}</span>
                  <span className="font-mono text-[10px] text-[#DC2626]">-{c.removed}</span>
                </div>
              </div>
              <p className="mt-2 text-[11px] leading-relaxed text-gray-500">{c.reason}</p>
              <DiffView diff={c.diff} />
            </div>
          );
        })}
      </div>
      {review && (
        <div className="panel p-5">
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill status={review.verdict} />
            <h3 className="panel-title">Changes / Critic review</h3>
            <span className="ml-auto text-[12px] font-semibold text-[#4F46E5]">{review.score}%</span>
          </div>
          <p className="mt-3 text-sm text-gray-600">{review.summary}</p>
          {review.issues.length > 0 && (
            <ul className="mt-3 space-y-1 text-[12px] text-[#B45309]">
              {review.issues.map((s, i) => (
                <li key={i}>• {String(s)}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {hasChanges && (
        <div className="panel flex flex-wrap items-center gap-4 p-5">
          <div>
            <h3 className="text-[13px] font-semibold text-gray-900">Ship this fix</h3>
            <p className="mt-0.5 text-[11px] text-gray-500">
              {gh?.enabled ? "Open a GitHub PR with the verified changes and full evidence body." : "Configure GITHUB_TOKEN and GITHUB_REPO to enable PR shipping."}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {prErr && <span className="text-[11px] text-[#DC2626]">{prErr}</span>}
            {prUrl && (
              <a href={prUrl} target="_blank" rel="noreferrer" className="text-[12px] font-semibold text-[#4F46E5] underline">
                PR opened ↗
              </a>
            )}
            <button
              onClick={openPr}
              disabled={!gh?.enabled || loadingPr}
              className="rounded-lg bg-[#4F46E5] px-4 py-2 text-[12px] font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loadingPr ? "Opening…" : gh?.enabled ? "Open GitHub PR" : "Not configured"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function TestsPanel({ report }: { report: MissionReport | null }) {
  const byPhase = useMemo(() => {
    if (!report) return {};
    const groups: Record<string, { passed: number; failed: number; rows: typeof report.tests }> = {};
    for (const t of report.tests) {
      const g = groups[t.phase] ?? { passed: 0, failed: 0, rows: [] };
      if (t.status === "passed") g.passed += 1;
      else g.failed += 1;
      g.rows.push(t);
      groups[t.phase] = g;
    }
    return groups;
  }, [report]);

  if (!report) return null;

  return (
    <div className="space-y-4">
      {Object.entries(byPhase).map(([phase, g]) => (
        <div key={phase} className="panel p-5">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="panel-title">{phase} phase</h3>
            <span className="font-mono text-[11px] text-[#059669]">{g.passed} passed</span>
            {g.failed > 0 && <span className="font-mono text-[11px] text-[#DC2626]">{g.failed} failed</span>}
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[12px]">
              <thead>
                <tr className="text-[11px] text-gray-500">
                  <th className="pb-2 pr-4 font-medium">Status</th>
                  <th className="pb-2 pr-4 font-medium">Test</th>
                  <th className="pb-2 font-medium">Path</th>
                </tr>
              </thead>
              <tbody>
                {g.rows.map((t, i) => (
                  <tr key={i} className="border-t border-[#F3F4F6]">
                    <td className="py-1.5 pr-4">
                      <span className="font-semibold" style={{ color: statusColor(t.status) }}>{t.status}</span>
                    </td>
                    <td className="py-1.5 pr-4 text-gray-900">{t.name}</td>
                    <td className="py-1.5 font-mono text-[11px] text-gray-500">{t.path}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

function SecurityPanel({ report }: { report: MissionReport | null }) {
  if (!report) return null;
  const counts = report.security_scan;
  const rows = [
    ["critical", counts.critical ?? 0, "#DC2626"],
    ["high", counts.high ?? 0, "#EA580C"],
    ["medium", counts.medium ?? 0, "#B45309"],
    ["low", counts.low ?? 0, "#0D9488"],
    ["info", counts.info ?? 0, "#6B7280"],
  ] as const;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-5 gap-3">
        {rows.map(([sev, n, color]) => (
          <div key={sev} className="panel p-4 text-center">
            <p className="text-2xl font-bold" style={{ color }}>{n}</p>
            <p className="mt-1 text-[11px] text-gray-500">{sev}</p>
          </div>
        ))}
      </div>
      <div className="space-y-3">
        {report.security.length === 0 && <p className="text-sm text-gray-400">No security findings recorded.</p>}
        {report.security.map((s, i) => (
          <div key={i} className="panel p-4">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityPill severity={s.severity} />
              <span className="font-mono text-[10px] text-gray-500">{s.rule}</span>
              <span className="ml-auto font-mono text-[11px] text-gray-500">{s.path}{s.line ? `:${s.line}` : ""}</span>
            </div>
            <h4 className="mt-2 text-sm font-semibold text-gray-900">{s.title}</h4>
            <p className="mt-1 text-[12px] leading-relaxed text-gray-600">{s.description}</p>
            {s.remediation && <p className="mt-2 text-[11px] text-[#0D9488]">→ {s.remediation}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

function ReleaseGatePanel({ report }: { report: MissionReport | null }) {
  if (!report) return null;
  if (report.release_gate.checks.length === 0)
    return <div className="panel p-6 text-center text-sm text-gray-400">Release processing…</div>;
  const overall = report.release_gate.overall;
  const ready = overall === "ready";
  const color = statusColor(overall);
  return (
    <div className="panel p-6">
      <div className="flex items-center gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl" style={{ background: `${color}10`, border: `1px solid ${color}30` }}>
          {ready ? (
            <CheckCircle2 className="h-7 w-7" style={{ color }} />
          ) : (
            <Gavel className="h-7 w-7" style={{ color }} />
          )}
        </div>
        <div>
          <h3 className="text-lg font-bold" style={{ color }}>{overall === "ready" ? "Ready" : overall.replace("_", " ")}</h3>
          <p className="text-[11px] text-gray-500">Release gate · {report.release_gate.checks.length} checks</p>
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {report.release_gate.checks.map((g) => {
          const c = statusColor(g.status);
          return (
            <div key={g.name} className="flex items-start gap-3 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-4">
              <StatusPill status={g.status} />
              <div>
                <p className="font-mono text-[12px] font-semibold text-gray-900">{g.name.replace("_", " ")}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-gray-600">{g.detail}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ReportPanel({ report }: { report: MissionReport | null }) {
  if (!report) return null;
  const highlights = report.metrics.filter((m) => ["workflow_duration_ms", "tests_generated", "tests_executed", "files_investigated", "security_findings", "files_changed", "human_approvals", "manual_baseline_min", "forge_workflow_min", "agents_executed", "skills_matched"].includes(m.key));
  const matched = report.skills?.filter((s) => s.matched) ?? [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {highlights.slice(0, 10).map((m) => (
          <div key={m.key} className="panel p-4">
            <p className="font-mono text-lg font-bold text-[#4F46E5]">{m.value}{m.unit === "ms" ? "ms" : m.unit === "min" ? "m" : m.unit ? "×" : ""}</p>
            <p className="mt-1 text-[11px] text-gray-600">{m.label}</p>
            <p className="mt-1 font-mono text-[10px] text-gray-400">{m.source}</p>
          </div>
        ))}
      </div>
      <div className="panel p-5">
        <h3 className="panel-title">Mission summary</h3>
        <p className="mt-3 text-[14px] leading-relaxed text-gray-700">{report.summary}</p>
        <div className="mt-4 flex flex-wrap gap-6 text-[12px] text-gray-500">
          <span className="font-mono">Repo <span className="text-gray-900">{report.repository.name}</span></span>
          <span className="font-mono">Files <span className="text-gray-900">{String(report.repository.stats.files ?? 0)}</span></span>
          <span className="font-mono">Lines <span className="text-gray-900">{String(report.repository.stats.lines ?? 0)}</span></span>
          <span className="font-mono">Tests <span className="text-gray-900">{String(report.repository.stats.tests ?? 0)}</span></span>
          <span className="font-mono">Components <span className="text-gray-900">{String(report.repository.stats.components ?? 0)}</span></span>
        </div>
      </div>
      {matched.length > 0 && (
        <div className="panel p-5">
          <h3 className="panel-title">Skills applied</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {matched.map((s) => (
              <div key={s.id} className="rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-semibold text-gray-900">{s.name}</span>
                  <Pill text={s.id} color="#4F46E5" />
                </div>
                <p className="mt-2 text-[12px] leading-relaxed text-gray-600">{s.description}</p>
                <p className="mt-3 font-mono text-[11px] text-gray-500">
                  {s.observations} probes · patches: {s.patches.join(", ")}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ActivityPanel({ report }: { report: MissionReport | null }) {
  if (!report) return null;
  return (
    <div className="panel p-5">
      <h3 className="panel-title">Audit trail</h3>
      <div className="mt-4 space-y-2.5">
        {report.activity.map((a, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: Math.min(i * 0.02, 0.4) }}
            className="flex items-start gap-3"
          >
            <span className="mt-0.5 font-mono text-[10px] text-gray-400">{new Date(a.at).toLocaleTimeString()}</span>
            <span className="mt-0.5 min-w-[76px] font-mono text-[10px] font-semibold text-[#4F46E5]">{a.agent}</span>
            <span className="text-[12px] leading-relaxed text-gray-700">{a.message}</span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function PrintSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="print-page-break">
      <h2 className="mb-1 text-[13px] font-bold uppercase tracking-wide text-gray-500">{title}</h2>
      <div className="border-t border-gray-300 pt-2">{children}</div>
    </section>
  );
}

function PrintReport({ mission, report }: { mission: MissionDetail; report: MissionReport }) {
  const gate = report.release_gate;
  const review = report.reviews[0];
  const counts = report.security_scan;
  const matched = report.skills?.filter((s) => s.matched) ?? [];

  return (
    <div className="print-block print-monoreport">
      <div className="pb-4">
        <h1 className="text-[18px] font-bold text-gray-900">FORGE — Engineering Report</h1>
        <p className="mt-1 text-[11px] text-gray-600">Autonomous engineering control plane · evidence-driven mission report</p>
      </div>

      <table>
        <tbody>
          <tr><th style={{ width: "150px" }}>Mission</th><td>{mission.title}</td></tr>
          <tr><th>Mission ID</th><td>{mission.id}</td></tr>
          <tr><th>Repository</th><td>{report.repository.name}</td></tr>
          <tr><th>Status</th><td>{mission.status} · {mission.gate_overall || "—"}</td></tr>
          <tr><th>Duration</th><td>{fmtMs(mission.duration_ms)}</td></tr>
          <tr><th>Completed</th><td>{mission.completed_at ? new Date(mission.completed_at).toLocaleString() : "—"}</td></tr>
          <tr><th>Repo stats</th><td>{String(report.repository.stats.files ?? 0)} files · {String(report.repository.stats.lines ?? 0)} lines · {String(report.repository.stats.tests ?? 0)} tests · {String(report.repository.stats.components ?? 0)} components</td></tr>
        </tbody>
      </table>

      <section className="print-page-break">
        <h2 className="mb-1 text-[13px] font-bold uppercase tracking-wide text-gray-500">Summary</h2>
        <div className="border-t border-gray-300 pt-2">
          <p className="text-[12px] leading-relaxed text-gray-800">{report.summary}</p>
        </div>
      </section>

      {report.root_cause && (
        <PrintSection title="Root cause">
          <p className="text-[13px] font-bold text-gray-900">{report.root_cause.title}</p>
          <p className="mt-1 font-mono text-[11px] leading-relaxed text-gray-700">{report.root_cause.detail}</p>
          <p className="mt-1 text-[10px] text-gray-500">
            {report.root_cause.file}{report.root_cause.line ? `:${report.root_cause.line}` : ""} · {Math.round(report.root_cause.confidence * 100)}% confidence · {report.root_cause.agent}
          </p>
        </PrintSection>
      )}

      {report.findings.length > 0 && (
        <PrintSection title="Findings">
          <table>
            <thead><tr><th>Severity</th><th>Category</th><th>Finding</th><th>File</th><th>Agent</th></tr></thead>
            <tbody>
              {report.findings.map((f, i) => (
                <tr key={i}>
                  <td>{f.severity}</td>
                  <td>{f.category}</td>
                  <td>
                    <span className="font-semibold text-gray-900">{f.title}</span>
                    <div className="text-[10px] text-gray-600">{f.detail}</div>
                  </td>
                  <td>{f.file}{f.line ? `:${f.line}` : ""}</td>
                  <td>{f.agent}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </PrintSection>
      )}

      {report.code_changes.length > 0 && (
        <PrintSection title="Code changes">
          {report.code_changes.map((c, i) => (
            <div key={i} className="mb-3">
              <p className="font-mono text-[11px] font-bold text-gray-900">{c.path} <span className="font-normal text-green-700">+{c.added}</span> <span className="font-normal text-red-700">-{c.removed}</span></p>
              <p className="text-[10px] text-gray-600">{c.reason}</p>
              <pre className="mt-1 bg-[#F9FAFB] p-2 font-mono text-[10px] leading-relaxed text-gray-800">{c.diff}</pre>
            </div>
          ))}
        </PrintSection>
      )}

      {review && (
        <PrintSection title="Critic review">
          <p className="text-[12px] font-semibold text-gray-900">{review.reviewer}: {review.verdict} — {review.score}%</p>
          <p className="mt-1 text-[11px] text-gray-700">{review.summary}</p>
          {review.issues.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-[10px] text-amber-700">
              {review.issues.map((s, i) => <li key={i}>{String(s)}</li>)}
            </ul>
          )}
        </PrintSection>
      )}

      {report.tests.length > 0 && (
        <PrintSection title="Tests">
          <table>
            <thead><tr><th>Status</th><th>Phase</th><th>Test</th><th>Path</th></tr></thead>
            <tbody>
              {report.tests.map((t, i) => (
                <tr key={i}>
                  <td>{t.status}</td>
                  <td>{t.phase}</td>
                  <td>{t.name}</td>
                  <td>{t.path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </PrintSection>
      )}

      <PrintSection title="Security scan">
        <p className="text-[11px] text-gray-700">
          {counts.critical ?? 0} critical · {counts.high ?? 0} high · {counts.medium ?? 0} medium · {counts.low ?? 0} low · {counts.info ?? 0} info
        </p>
        {report.security.length > 0 && (
          <table className="mt-2">
            <thead><tr><th>Severity</th><th>Rule</th><th>Finding</th><th>Path</th></tr></thead>
            <tbody>
              {report.security.map((s, i) => (
                <tr key={i}>
                  <td>{s.severity}</td>
                  <td>{s.rule}</td>
                  <td>
                    <span className="font-semibold text-gray-900">{s.title}</span>
                    <div className="text-[10px] text-gray-600">{s.description}</div>
                  </td>
                  <td>{s.path}{s.line ? `:${s.line}` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </PrintSection>

      <PrintSection title="Release gate">
        <p className="text-[12px] font-semibold text-gray-900">Overall: {gate.overall}</p>
        <table className="mt-1">
          <thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead>
          <tbody>
            {gate.checks.map((g) => (
              <tr key={g.order_index}>
                <td>{g.name.replace(/_/g, " ")}</td>
                <td>{g.status}</td>
                <td>{g.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </PrintSection>

      {matched.length > 0 && (
        <PrintSection title="Skills applied">
          {matched.map((s) => (
            <p key={s.id} className="text-[11px] text-gray-700">
              <span className="font-semibold text-gray-900">{s.name}</span> ({s.id}) — {s.description}
            </p>
          ))}
        </PrintSection>
      )}

      {report.evidence.length > 0 && (
        <PrintSection title="Evidence">
          <table>
            <thead><tr><th>Agent</th><th>Kind</th><th>Label</th><th>Source</th></tr></thead>
            <tbody>
              {report.evidence.map((e, i) => (
                <tr key={i}>
                  <td>{e.agent}</td>
                  <td>{e.kind}</td>
                  <td>{e.label}</td>
                  <td>{e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </PrintSection>
      )}

      {report.activity.length > 0 && (
        <PrintSection title="Audit trail">
          <table>
            <thead><tr><th>At</th><th>Agent</th><th>Event</th></tr></thead>
            <tbody>
              {report.activity.map((a, i) => (
                <tr key={i}>
                  <td>{new Date(a.at).toLocaleString()}</td>
                  <td>{a.agent}</td>
                  <td>{a.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </PrintSection>
      )}

      <section className="print-page-break mt-6">
        <p className="text-[9px] text-gray-400">
          Generated by FORGE — every finding, test count and gate outcome is recorded deterministically from real execution.
        </p>
      </section>
    </div>
  );
}

export default function MissionControl({ missionId }: { missionId: string }) {
  const [mission, setMission] = useState<MissionDetail | null>(null);
  const [report, setReport] = useState<MissionReport | null>(null);
  const [tab, setTab] = useState<Tab>("root");
  const [error, setError] = useState<string>("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const m = await api.mission(missionId);
        if (stopped) return;
        setMission(m);
        if (m.status === "completed") {
          const r = await api.report(missionId);
          if (!stopped) setReport(r);
          if (pollRef.current) clearInterval(pollRef.current);
        } else if (m.status === "failed") {
          setError(m.error || "Mission failed.");
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {
        if (!stopped) setError("Could not reach the FORGE API on localhost:8000.");
      }
    };
    tick();
    pollRef.current = setInterval(tick, 1200);
    return () => {
      stopped = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [missionId]);

  if (error && !mission) {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <div className="panel max-w-md p-8 text-center">
          <Fingerprint className="mx-auto h-8 w-8 text-[#DC2626]" />
          <h1 className="mt-4 text-lg font-bold text-gray-900">API unreachable</h1>
          <p className="mt-2 text-sm text-gray-600">{error}</p>
          <p className="mt-3 font-mono text-[11px] text-gray-500">
            Start the backend: <span className="text-[#0D9488]">uvicorn app.main:app --port 8000</span>
          </p>
        </div>
      </main>
    );
  }

  const agents = mission?.agents ?? [];
  const reportSummary = report ?? null;

  return (
    <main className="min-h-screen">
      {report && mission && <PrintReport mission={mission} report={report} />}
      <div className="no-print mx-auto max-w-7xl px-6 py-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#E5E7EB] bg-white transition-colors hover:border-[#4F46E5]/50">
              <ArrowLeft className="h-4 w-4 text-gray-500" />
            </Link>
            <Link href="/" className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#E5E7EB] bg-white transition-colors hover:border-[#4F46E5]/50">
                <Flame className="h-5 w-5 text-[#4F46E5]" />
              </div>
              <span className="hidden text-[16px] font-bold tracking-tight text-gray-900 sm:inline">
                FORGE<span className="text-[#4F46E5]">.</span>
              </span>
            </Link>
            <div>
              <h1 className="text-lg font-bold leading-tight text-gray-900">{mission?.title ?? "Mission"}</h1>
              <p className="mt-0.5 font-mono text-[11px] text-gray-500">{missionId}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {mission && <StatusPill status={mission.status} />}
            {mission?.gate_overall && mission.status === "completed" && <Pill text={mission.gate_overall} color="#059669" />}
            <button
              onClick={() => window.print()}
              disabled={!report}
              title="Export this report as a PDF (via the print dialog → Save as PDF)"
              className="flex items-center gap-2 rounded-lg border border-[#E5E7EB] bg-white px-3 py-1.5 text-[12px] font-semibold text-gray-700 transition-colors hover:border-[#4F46E5]/50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Printer className="h-3.5 w-3.5" />
              Export PDF
            </button>
          </div>
        </header>

        {mission && (
          <div className="mt-6 bg-white">
            <div className="panel flex items-center gap-4 p-5">
              <span className="text-[11px] font-medium text-gray-500">Progress</span>
              <div className="flex-1"><ProgressBar value={mission.progress} color={mission.status === "completed" ? "#059669" : "#4F46E5"} /></div>
              <span className="font-mono text-[11px] text-gray-600">{Math.round(mission.progress * 100)}%</span>
              <span className="font-mono text-[11px] text-gray-500">{fmtMs(mission.duration_ms)}</span>
            </div>
          </div>
        )}

        {/* evidence graph */}
        {report ? (
          <div className="mt-6">
            <EvidenceGraph nodes={report.evidence_graph.nodes} edges={report.evidence_graph.edges} />
          </div>
        ) : (
          mission && (
            <div className="mt-6 panel p-5">
              <EvidenceGraph
                nodes={[
                  { id: "mission", label: "Mission", kind: "mission", status: mission.status, count: 0, detail: mission.status },
                  { id: "evidence", label: "Evidence", kind: "evidence", status: mission.status, count: 0, detail: "" },
                  { id: "root-cause", label: "Root cause", kind: "analysis", status: mission.status, count: 0, detail: "" },
                  { id: "changes", label: "Changes", kind: "change", status: mission.status, count: 0, detail: "" },
                  { id: "tests", label: "Tests", kind: "validate", status: mission.status, count: 0, detail: "" },
                  { id: "security", label: "Security", kind: "validate", status: mission.status, count: 0, detail: "" },
                  { id: "critic", label: "Critic review", kind: "review", status: "pending", count: 0, detail: "" },
                  { id: "release", label: "Release gate", kind: "gate", status: "pending", count: 0, detail: "" },
                ]}
                edges={[
                  { source: "mission", target: "evidence", kind: "flow" },
                  { source: "evidence", target: "root-cause", kind: "flow" },
                  { source: "root-cause", target: "changes", kind: "flow" },
                  { source: "changes", target: "tests", kind: "flow" },
                  { source: "changes", target: "security", kind: "flow" },
                  { source: "tests", target: "critic", kind: "flow" },
                  { source: "security", target: "critic", kind: "flow" },
                  { source: "critic", target: "release", kind: "flow" },
                ]}
              />
            </div>
          )
        )}

        {/* agent strip */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {["architect", "debugger", "security", "tester", "actor", "critic", "release"].map((name) => {
            const runs = agents.filter((a: AgentRun) => a.agent === name);
            const a = runs[runs.length - 1];
            const color = a ? statusColor(a.status) : "#D1D5DB";
            return (
              <div key={name} className="panel p-4" style={{ borderColor: a ? `${color}30` : "#E5E7EB" }}>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] font-semibold" style={{ color: a ? color : "#6B7280" }}>{name[0].toUpperCase() + name.slice(1)}</span>
                  {a && <span className="font-mono text-[10px] text-gray-500">{fmtMs(a.duration_ms)}</span>}
                </div>
                {a ? (
                  <p className="mt-1.5 line-clamp-2 text-[11px] leading-snug text-gray-600">{a.summary}</p>
                ) : (
                  <p className="mt-1.5 text-[11px] text-gray-400">Awaiting allocation…</p>
                )}
              </div>
            );
          })}
        </div>

        {/* tabs */}
        <nav className="mt-8 flex flex-wrap gap-1 border-b border-[#E5E7EB] pb-3">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors"
              style={{
                background: tab === t.id ? "#F3F4F6" : "transparent",
                color: tab === t.id ? "#111827" : "#6B7280",
              }}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </nav>

        <div className="mt-6">
          <AnimatePresence mode="wait">
            <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.14 }}>
              {tab === "root" && <RootCausePanel mission={mission} report={reportSummary} />}
              {tab === "findings" && <FindingsPanel report={reportSummary} />}
              {tab === "critic" && <CriticPanel report={reportSummary} oid={missionId} />}
              {tab === "tests" && <TestsPanel report={reportSummary} />}
              {tab === "security" && <SecurityPanel report={reportSummary} />}
              {tab === "gate" && <ReleaseGatePanel report={reportSummary} />}
              {tab === "report" && <ReportPanel report={reportSummary} />}
              {tab === "activity" && <ActivityPanel report={reportSummary} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </main>
  );
}