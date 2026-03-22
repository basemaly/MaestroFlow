import type { ExecutiveSystemStatus } from "@/core/executive/types";

export type DiagnosticsLogComponent = {
  component_id: string;
  label: string;
  path: string;
  exists: boolean;
  size_bytes: number;
  updated_at?: string | null;
};

export type DiagnosticsLogLine = {
  timestamp?: string | null;
  level?: string | null;
  logger?: string | null;
  service?: string | null;
  request_id?: string | null;
  trace_id?: string | null;
  message?: string | null;
  raw: string;
};

export type DiagnosticsRequestEntry = {
  timestamp?: string | null;
  service?: string | null;
  request_id?: string | null;
  trace_id?: string | null;
  kind: "complete" | "failed";
  method: string;
  path: string;
  status?: number | null;
  duration_ms?: number | null;
  message: string;
  raw?: string | null;
};

export type DiagnosticsTraceEntry = {
  trace_id: string;
  last_seen_at?: string | null;
  request_count: number;
  paths: string[];
  latest_status?: number | null;
  latest_request_id?: string | null;
};

export type DiagnosticsEventEntry = {
  event_kind: "audit" | "approval";
  event_id: string;
  timestamp: string;
  title: string;
  summary: string;
  status: string;
  component_id: string;
  action_id: string;
  details: Record<string, unknown>;
};

export type DiagnosticsOverview = {
  generated_at: string;
  runtime: {
    frontend_mode: "app" | "ui-dev" | string;
  };
  status: ExecutiveSystemStatus;
  summary: {
    warnings: number;
    log_components: number;
    recent_requests: number;
    recent_traces: number;
    recent_events: number;
  };
  signals: {
    gateway_warnings: number;
    gateway_errors: number;
    plan_review: {
      count: number;
      latest_duration_ms?: number | null;
      max_duration_ms?: number | null;
    };
  };
  sections: {
    logs: {
      component_count: number;
      items: DiagnosticsLogComponent[];
    };
    requests: {
      items: DiagnosticsRequestEntry[];
    };
    traces: {
      items: DiagnosticsTraceEntry[];
    };
    events: {
      items: DiagnosticsEventEntry[];
    };
  };
};
