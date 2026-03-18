"use client";

import Galaxy from "@/components/ui/galaxy";
import { cn } from "@/lib/utils";

export function DeerIntroOverlay({
  active,
  className,
}: {
  active: boolean;
  className?: string;
}) {
  if (!active) {
    return null;
  }

  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 -z-10 overflow-hidden",
        className,
      )}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.04),_transparent_30%),linear-gradient(180deg,rgba(10,14,22,0.38)_0%,rgba(10,14,22,0.12)_42%,rgba(10,14,22,0)_100%)]" />
      <div className="absolute inset-0 opacity-[0.34]">
        <Galaxy
          mouseRepulsion={false}
          starSpeed={0.08}
          density={0.28}
          glowIntensity={0.1}
          twinkleIntensity={0.12}
          speed={0.2}
        />
      </div>
      <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-background/38 to-transparent" />
    </div>
  );
}
