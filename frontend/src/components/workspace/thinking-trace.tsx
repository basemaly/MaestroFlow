"use client";

import { ChevronDownIcon } from "lucide-react";
import { useState } from "react";

export function ThinkingTrace({ thoughts }: { thoughts: string[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!thoughts.length) return null;

  return (
    <div className="mb-4 border border-amber-500/20 bg-amber-500/5 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3 hover:bg-amber-500/10 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="size-2 rounded-full bg-amber-500 animate-pulse" />
          <span className="text-sm font-medium text-amber-700 dark:text-amber-300">
            Thinking
          </span>
          <span className="text-xs text-amber-600/60 dark:text-amber-400/60">
            {thoughts.length} step{thoughts.length !== 1 ? "s" : ""}
          </span>
        </div>
        <ChevronDownIcon
          className="size-4 text-amber-600/60 transition-transform"
          style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)" }}
        />
      </button>

      {expanded && (
        <div className="border-t border-amber-500/20 px-4 py-3 space-y-2 bg-amber-500/2.5">
          {thoughts.map((thought, i) => (
            <div key={i} className="flex gap-3">
              <div className="text-xs font-medium text-amber-600/60 dark:text-amber-400/60 mt-1">
                {i + 1}.
              </div>
              <p className="text-sm text-amber-700/80 dark:text-amber-300/80 leading-relaxed">
                {thought}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
