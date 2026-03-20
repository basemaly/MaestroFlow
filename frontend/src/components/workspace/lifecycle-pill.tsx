"use client";

import { CheckCircle2Icon, Clock3Icon, Loader2Icon, AlertCircleIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const toneClasses = {
  idle: "border-slate-400/25 bg-slate-500/10 text-slate-700 dark:text-slate-300",
  working: "border-amber-400/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  success: "border-emerald-400/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  error: "border-red-400/30 bg-red-500/10 text-red-700 dark:text-red-300",
} as const;

export function LifecyclePill({
  tone,
  label,
  detail,
  className,
}: {
  tone: keyof typeof toneClasses;
  label: string;
  detail?: string;
  className?: string;
}) {
  const Icon = tone === "working"
    ? Loader2Icon
    : tone === "success"
      ? CheckCircle2Icon
      : tone === "error"
        ? AlertCircleIcon
        : Clock3Icon;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs",
        toneClasses[tone],
        className,
      )}
    >
      <Icon className={cn("size-3.5", tone === "working" && "animate-spin")} />
      <span className="font-medium">{label}</span>
      {detail ? <span className="opacity-80">{detail}</span> : null}
    </div>
  );
}
