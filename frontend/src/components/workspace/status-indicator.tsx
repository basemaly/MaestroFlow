"use client";

import { CheckCircleIcon, AlertCircleIcon, Loader2Icon } from "lucide-react";

type StatusType = "idle" | "loading" | "success" | "error";

interface StatusIndicatorProps {
  status: StatusType;
  message?: string;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

const statusConfig = {
  idle: {
    icon: CheckCircleIcon,
    color: "text-slate-500",
    label: "Ready",
  },
  loading: {
    icon: Loader2Icon,
    color: "text-blue-500",
    label: "Loading",
  },
  success: {
    icon: CheckCircleIcon,
    color: "text-emerald-500",
    label: "Success",
  },
  error: {
    icon: AlertCircleIcon,
    color: "text-red-500",
    label: "Error",
  },
};

const sizeConfig = {
  sm: { icon: "size-3", outer: "size-6" },
  md: { icon: "size-4", outer: "size-8" },
  lg: { icon: "size-5", outer: "size-10" },
};

export function StatusIndicator({
  status,
  message,
  size = "md",
  showLabel = false,
}: StatusIndicatorProps) {
  const config = statusConfig[status];
  const sizes = sizeConfig[size];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2">
      <div className={`flex items-center justify-center ${sizes.outer}`}>
        <Icon
          className={`${sizes.icon} ${config.color} ${status === "loading" ? "animate-spin" : ""}`}
        />
      </div>
      {(showLabel || message) && (
        <span className="text-xs text-muted-foreground">
          {message || config.label}
        </span>
      )}
    </div>
  );
}
