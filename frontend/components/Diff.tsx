"use client";

import { memo } from "react";

function classify(line: string): { cls: string; content: string } {
  if (line.startsWith("+++") || line.startsWith("---")) return { cls: "diff-ctx", content: line };
  if (line.startsWith("+")) return { cls: "diff-add", content: line };
  if (line.startsWith("-")) return { cls: "diff-sub", content: line };
  if (line.startsWith("@@")) return { cls: "diff-ctx", content: line };
  return { cls: "diff-ctx", content: line };
}

export const DiffView = memo(function DiffView({ diff }: { diff: string }) {
  const lines = diff.split("\n");
  return (
    <div className="code-block mt-3 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-3 text-[12px]">
      {lines.map((l, i) => {
        const { cls, content } = classify(l);
        return (
          <div key={i} className={cls}>
            {content || " "}
          </div>
        );
      })}
    </div>
  );
});