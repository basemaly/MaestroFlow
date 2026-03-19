"use client";

export function MessageLoader() {
  return (
    <div className="flex items-start gap-3 py-4">
      <div className="mt-1 size-6 rounded-full bg-foreground/10" />
      <div className="flex-1 space-y-2">
        <div className="space-y-2">
          {/* Three animated skeleton lines */}
          <div className="h-4 w-3/4 animate-pulse rounded bg-foreground/10" />
          <div className="h-4 w-full animate-pulse rounded bg-foreground/10" />
          <div className="h-4 w-4/5 animate-pulse rounded bg-foreground/10" />
        </div>
        {/* Thinking indicator */}
        <div className="mt-3 flex items-center gap-2">
          <div className="size-2 rounded-full bg-amber-500 animate-pulse" />
          <span className="text-xs text-amber-600 dark:text-amber-400">
            Thinking...
          </span>
        </div>
      </div>
    </div>
  );
}
