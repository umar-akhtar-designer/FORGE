"use client";

import { severityColor, statusColor } from "@/lib/format";

export function Pill({ text, color }: { text: string; color: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
      style={{ color, background: `${color}10`, border: `1px solid ${color}30` }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {text}
    </span>
  );
}

export function SeverityPill({ severity }: { severity: string }) {
  return <Pill text={severity} color={severityColor(severity)} />;
}

export function StatusPill({ status }: { status: string }) {
  return <Pill text={status.replace("_", " ")} color={statusColor(status)} />;
}

export function ProgressBar({ value, color = "#4F46E5" }: { value: number; color?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#E5E7EB]">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${Math.round(value * 100)}%`, background: color }}
      />
    </div>
  );
}