"use client";

import { memo } from "react";

import { cn } from "@/lib/utils";

export const ExecutiveIcon = memo(function ExecutiveIcon({
  className,
  size = "md",
}: {
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const sizeClasses = {
    sm: "text-2xl",
    md: "text-4xl",
    lg: "text-5xl",
    xl: "text-6xl",
  };

  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex select-none items-center justify-center font-serif leading-none text-amber-500 transition-all duration-200",
        sizeClasses[size],
        "hover:text-amber-400 hover:scale-110",
        className,
      )}
    >
      𝄞
    </span>
  );
});
