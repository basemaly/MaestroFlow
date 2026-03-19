export type ActivepiecesState =
  | "healthy"
  | "degraded"
  | "unavailable"
  | "misconfigured"
  | "disabled"
  | "unknown";

export interface ActivepiecesHealth {
  configured: boolean;
  available: boolean;
  healthy: boolean;
  summary: string;
  last_error?: string | null;
}

export interface ActivepiecesConfigResponse {
  base_url: string;
  enabled: boolean;
  configured: boolean;
  available: boolean;
  warning?: string | null;
  health?: ActivepiecesHealth;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface ActivepiecesFlow {
  flow_id: string;
  label: string;
  description: string;
  component_scope: string[];
  approval_required: boolean;
  input_contract: Record<string, unknown>;
  enabled: boolean;
  status?: string | null;
  last_run_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ActivepiecesFlowsResponse {
  flows: ActivepiecesFlow[];
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface ActivepiecesFlowPreviewResponse {
  available: boolean;
  can_trigger: boolean;
  flow_id: string;
  summary: string;
  input_preview: Record<string, unknown>;
  approval_required: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface ActivepiecesFlowTriggerResponse {
  available: boolean;
  flow_id: string;
  status: string;
  summary: string;
  run_id?: string | null;
  approval_id?: string | null;
  result?: Record<string, unknown> | null;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface ActivepiecesWebhookResponse {
  available: boolean;
  accepted: boolean;
  summary: string;
  run_id?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}
