"use client";

import { cn } from "@/lib/utils";

export function ExecutiveIcon({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex select-none items-center justify-center font-serif leading-none text-amber-500",
        className,
      )}
    >
      𝄞
    </span>
  );
}
