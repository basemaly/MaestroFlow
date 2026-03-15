"use client";

import { useEffect, useState } from "react";

import { FlickeringGrid } from "@/components/ui/flickering-grid";
import Galaxy from "@/components/ui/galaxy";
import { cn } from "@/lib/utils";

export function DeerIntroOverlay({
  active,
  className,
}: {
  active: boolean;
  className?: string;
}) {
  const [visible, setVisible] = useState(false);
  const [hasCheckedSession, setHasCheckedSession] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const seen = window.sessionStorage.getItem("maestroflow-deer-intro-seen");
    if (seen === "1") {
      setVisible(false);
    }
    setHasCheckedSession(true);
  }, []);

  useEffect(() => {
    if (!hasCheckedSession) {
      return;
    }

    if (!active) {
      setVisible(false);
      return;
    }

    if (window.sessionStorage.getItem("maestroflow-deer-intro-seen") === "1") {
      setVisible(false);
      return;
    }

    setVisible(true);
    window.sessionStorage.setItem("maestroflow-deer-intro-seen", "1");
    const timer = window.setTimeout(() => {
      setVisible(false);
    }, 3000);

    return () => window.clearTimeout(timer);
  }, [active, hasCheckedSession]);

  // Intro overlay permanently disabled
  return null;

  // eslint-disable-next-line no-unreachable
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 z-0 overflow-hidden transition-opacity duration-1200",
        visible ? "opacity-100" : "opacity-0",
        className,
      )}
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-black/10">
        <Galaxy
          mouseRepulsion={false}
          starSpeed={0.14}
          density={0.42}
          glowIntensity={0.22}
          twinkleIntensity={0.18}
          speed={0.35}
        />
      </div>
      <FlickeringGrid
        className="absolute inset-0 translate-y-6 mask-[url(/images/deer.svg)] mask-size-[88vw] mask-center mask-no-repeat md:mask-size-[62vh]"
        squareSize={4}
        gridGap={4}
        color="white"
        maxOpacity={0.12}
        flickerChance={0.18}
      />
      <div className="absolute inset-0 bg-radial from-white/4 via-transparent to-transparent" />
      <div className="absolute top-0 right-0 left-0 h-32 bg-gradient-to-b from-background/55 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-56 bg-gradient-to-t from-background via-background/75 to-transparent" />
    </div>
  );
}
