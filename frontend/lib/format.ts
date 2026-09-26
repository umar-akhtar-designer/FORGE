import type { Severity } from "./types";

export function fmtDuration(ms: number): string {
  if (!ms || ms <= 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}m ${r}s`;
}

export function fmtMs(ms: number): string {
  if (!ms || ms <= 0) return "—";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

export function timeAgo(iso?: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - then);
  const s = Math.floor(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function severityColor(sev: Severity | string): string {
  switch (sev) {
    case "critical":
      return "#DC2626";
    case "high":
      return "#EA580C";
    case "medium":
      return "#B45309";
    case "low":
      return "#0D9488";
    default:
      return "#6B7280";
  }
}

export function statusColor(status: string): string {
  switch (status) {
    case "pass":
    case "completed":
    case "success":
    case "ready":
      return "#059669";
    case "fail":
    case "failed":
    case "blocked":
      return "#DC2626";
    case "running":
      return "#4F46E5";
    case "changes_requested":
      return "#B45309";
    case "queued":
      return "#9CA3AF";
    default:
      return "#6B7280";
  }
}

export const AGENT_NAMES: Record<string, string> = {
  architect: "Architect",
  debugger: "Debugger",
  security: "Security",
  tester: "Tester",
  actor: "Actor",
  critic: "Critic",
  release: "Release",
};