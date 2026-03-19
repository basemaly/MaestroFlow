"use client";

import { FlickeringGrid } from "@/components/ui/flickering-grid";

export function WorkspaceBackground() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.16),_transparent_35%),linear-gradient(180deg,rgba(7,10,18,0.15)_0%,rgba(7,10,18,0.04)_38%,rgba(7,10,18,0)_100%)]" />
      <div className="absolute left-1/2 top-[18%] h-[32rem] w-[32rem] -translate-x-1/2 rounded-full bg-amber-200/15 blur-3xl" />
      <div className="absolute right-[8%] top-[35%] h-[28rem] w-[28rem] rounded-full bg-amber-300/8 blur-3xl" />
      <FlickeringGrid
        className="absolute inset-0 opacity-[0.52] mix-blend-screen mask-[url(/images/deer.svg)] mask-size-[58vh] mask-position-[center_18%] mask-repeat-no-repeat xl:mask-size-[66vh]"
        squareSize={3}
        gridGap={5}
        color="rgb(255, 242, 204)"
        maxOpacity={0.32}
        flickerChance={0.11}
      />
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-background/40 to-transparent" />
    </div>
  );
}
