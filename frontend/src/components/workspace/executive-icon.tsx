"use client";

import { WaypointsIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function ExecutiveIcon({ className }: { className?: string }) {
  return <WaypointsIcon className={cn("text-amber-500", className)} />;
}
