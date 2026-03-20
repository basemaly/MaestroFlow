"use client";

import { memo } from "react";

import { FlickeringGrid } from "@/components/ui/flickering-grid";

export const MusicalBackground = memo(function MusicalBackground() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      {/* Warm musical gradient backdrop */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(217,119,6,0.12),_transparent_35%),linear-gradient(180deg,rgba(7,10,18,0.15)_0%,rgba(7,10,18,0.04)_38%,rgba(7,10,18,0)_100%)]" />

      {/* Soft amber glow (treble clef color) */}
      <div className="absolute left-1/2 top-[18%] h-[32rem] w-[32rem] -translate-x-1/2 rounded-full bg-amber-600/10 blur-3xl" />
      <div className="absolute right-[8%] top-[35%] h-[28rem] w-[28rem] rounded-full bg-amber-500/6 blur-3xl" />

      {/* Musical notes scattered (small decorative elements) */}
      <div className="absolute inset-0">
        {/* Note 1: top-left */}
        <div className="absolute left-[8%] top-[15%] text-amber-400/20 text-6xl font-serif">♪</div>
        {/* Note 2: top-right */}
        <div className="absolute right-[12%] top-[25%] text-amber-400/15 text-5xl font-serif">♫</div>
        {/* Note 3: bottom-right */}
        <div className="absolute right-[10%] bottom-[20%] text-amber-400/18 text-5xl font-serif">♪</div>
      </div>

      {/* Flickering grid with clef symbol mask */}
      <FlickeringGrid
        className="absolute inset-0 opacity-[0.48] mix-blend-screen [mask-image:radial-gradient(circle_at_center,rgba(0,0,0,0.8)_0%,rgba(0,0,0,0.4)_50%,rgba(0,0,0,0)_100%)]"
        squareSize={3}
        gridGap={5}
        color="rgb(251, 191, 36)"
        maxOpacity={0.28}
        flickerChance={0.13}
      />

      {/* Clef symbol watermark - centered, subtle */}
      <div className="absolute inset-0 flex items-center justify-center opacity-[0.12]">
        <div className="text-amber-500/40 text-[40rem] font-serif leading-none">𝄞</div>
      </div>

      {/* Top fade overlay */}
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-background/40 to-transparent" />
    </div>
  );
});
