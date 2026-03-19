export type BrowserRuntimeChoice = "auto" | "playwright" | "lightpanda";

export type BrowserJobAction = "navigate" | "extract" | "screenshot" | "script";

export type BrowserJobState =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "unknown";

export interface BrowserRuntimeHealth {
  configured: boolean;
  available: boolean;
  healthy: boolean;
  summary: string;
  last_error?: string | null;
}

export interface BrowserRuntimeConfigResponse {
  base_url: string;
  enabled: boolean;
  configured: boolean;
  available: boolean;
  default_runtime: BrowserRuntimeChoice;
  supported_runtimes: BrowserRuntimeChoice[];
  warning?: string | null;
  health?: BrowserRuntimeHealth;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface BrowserJobRequest {
  runtime?: BrowserRuntimeChoice;
  action: BrowserJobAction;
  url?: string;
  target?: string;
  input?: Record<string, unknown>;
  benchmark_id?: string | null;
}

export interface BrowserJobResult {
  job_id: string;
  runtime: BrowserRuntimeChoice;
  action: BrowserJobAction;
  status: BrowserJobState;
  url?: string | null;
  target?: string | null;
  summary: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BrowserRuntimeJobResponse {
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
  job: BrowserJobResult;
}

export interface BrowserRuntimeJobsResponse {
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
  jobs: BrowserJobResult[];
}
