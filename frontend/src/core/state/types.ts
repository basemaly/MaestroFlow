export type StateScope = "thread" | "project" | "experiment" | "workflow_route" | "unknown";

export type StateSnapshotFormat = "json" | "yaml" | "text";

export interface StateHealth {
  configured: boolean;
  available: boolean;
  healthy: boolean;
  summary: string;
  last_error?: string | null;
}

export interface StateConfigResponse {
  base_url: string;
  enabled: boolean;
  configured: boolean;
  available: boolean;
  warning?: string | null;
  health?: StateHealth;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface StateSnapshot {
  snapshot_id: string;
  scope: StateScope;
  reference_id?: string | null;
  label: string;
  summary?: string | null;
  state_type?: string | null;
  data?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface StateSnapshotsResponse {
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
  snapshots: StateSnapshot[];
}

export interface StateDiffChange {
  path: string;
  change_type: "added" | "removed" | "modified" | "unchanged" | "nested";
  summary?: string | null;
  before?: unknown;
  after?: unknown;
}

export interface StateDiffResponse {
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
  left_snapshot_id: string;
  right_snapshot_id: string;
  summary: string;
  changes: StateDiffChange[];
  left_snapshot?: StateSnapshot | null;
  right_snapshot?: StateSnapshot | null;
}

export interface StateExportResponse {
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
  snapshot_id: string;
  export_format: StateSnapshotFormat;
  payload: string | Record<string, unknown>;
}
