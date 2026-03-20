"use client";

import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getBackendBaseURL, getLangGraphBaseURL } from "@/core/config";

function describeRuntimeMode() {
  if (typeof window === "undefined") {
    return null;
  }

  const origin = window.location.origin;
  const host = window.location.hostname;
  const port = window.location.port || (window.location.protocol === "https:" ? "443" : "80");
  const backend = getBackendBaseURL() || `${origin}/api`;
  const langgraph = getLangGraphBaseURL(false);

  if ((host === "127.0.0.1" || host === "localhost") && port === "2027") {
    return {
      label: "Full Stack",
      tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-800",
      detail: `Public app ${origin} via nginx proxy\nGateway ${backend}\nLangGraph ${langgraph}`,
    };
  }

  if ((host === "127.0.0.1" || host === "localhost") && (port === "3010" || port === "3000")) {
    return {
      label: "Frontend Direct",
      tone: "border-amber-500/30 bg-amber-500/10 text-amber-800",
      detail: `Frontend dev origin ${origin}\nGateway ${backend}\nLangGraph ${langgraph}`,
    };
  }

  return {
    label: "Custom Route",
    tone: "border-zinc-500/30 bg-zinc-500/10 text-zinc-800",
    detail: `Origin ${origin}\nGateway ${backend}\nLangGraph ${langgraph}`,
  };
}

export function DevRuntimeBadge() {
  const runtime = useMemo(() => {
    if (process.env.NODE_ENV !== "development") {
      return null;
    }
    return describeRuntimeMode();
  }, []);

  if (!runtime) {
    return null;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className={`hidden rounded-full px-2.5 py-1 text-[11px] md:inline-flex ${runtime.tone}`}>
          {runtime.label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs whitespace-pre-line text-left">
        {runtime.detail}
      </TooltipContent>
    </Tooltip>
  );
}
