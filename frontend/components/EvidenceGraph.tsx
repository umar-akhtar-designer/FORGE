"use client";

import { motion } from "framer-motion";
import type { EvidenceGraphEdge, EvidenceGraphNode } from "@/lib/types";
import { statusColor } from "@/lib/format";

const KIND_COLOR: Record<string, string> = {
  mission: "#111827",
  evidence: "#4F46E5",
  analysis: "#EA580C",
  plan: "#B45309",
  change: "#4F46E5",
  validate: "#059669",
  review: "#0D9488",
  gate: "#059669",
};

const NODE_STEPS: Record<string, number> = {
  mission: 0,
  evidence: 1,
  "root-cause": 2,
  plan: 3,
  changes: 4,
  tests: 5,
  security: 6,
  critic: 7,
  release: 8,
};

export default function EvidenceGraph({
  nodes,
  edges,
}: {
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
}) {
  const ordered = [...nodes].sort((a, b) => (NODE_STEPS[a.id] ?? 99) - (NODE_STEPS[b.id] ?? 99));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edgeSet = new Set(edges.map((e) => `${e.source}:${e.target}`));

  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex min-w-max items-stretch gap-3">
        {ordered.map((n, i) => {
          const isDone = n.status === "completed" || n.status === "pass";
          const isRunning = n.status === "running";
          const color = isDone ? KIND_COLOR[n.kind] ?? "#059669" : n.status === "fail" ? "#DC2626" : "#D1D5DB";
          const next = ordered[i + 1];
          const hasEdge = next ? edgeSet.has(`${n.id}:${next.id}`) : false;
          return (
            <div key={n.id} className="flex items-stretch">
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="panel flex w-[150px] flex-col items-center justify-center gap-2 p-3 text-center"
                style={{ borderColor: isDone ? `${color}40` : "#E5E7EB" }}
              >
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-lg ${isRunning ? "animate-pulse" : ""}`}
                  style={{ background: `${color}10`, color, border: `1px solid ${color}30` }}
                >
                  <span className="text-sm font-bold">{n.count > 0 ? n.count : String(i + 1)}</span>
                </div>
                <span className="text-[11px] font-semibold" style={{ color }}>{n.label}</span>
                <span className="text-[10px] text-gray-400">{n.detail}</span>
              </motion.div>
              {hasEdge && next ? (
                <div className="flex items-center px-1.5">
                  <motion.div
                    animate={{ opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.15 }}
                    className="h-px w-5"
                    style={{ background: isDone ? "#059669" : "#D1D5DB" }}
                  />
                </div>
              ) : next ? (
                <div className="flex items-center px-1.5">
                  <div className="h-px w-5 bg-[#E5E7EB]" />
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}