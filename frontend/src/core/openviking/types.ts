export type OpenVikingState =
  | "healthy"
  | "degraded"
  | "unavailable"
  | "misconfigured"
  | "disabled"
  | "unknown";

export interface OpenVikingHealth {
  configured: boolean;
  available: boolean;
  healthy: boolean;
  summary: string;
  last_error?: string | null;
}

export interface OpenVikingConfigResponse {
  base_url: string;
  enabled: boolean;
  configured: boolean;
  available: boolean;
  warning?: string | null;
  health?: OpenVikingHealth;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface OpenVikingContextPack {
  pack_id: string;
  title: string;
  description: string;
  references: string[];
  skills: string[];
  prompts: string[];
  source?: string | null;
  source_key?: string | null;
  source_url?: string | null;
  fingerprint?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface OpenVikingSearchResponse {
  items: OpenVikingContextPack[];
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface OpenVikingAttachResponse {
  items: OpenVikingContextPack[];
  attached: number;
  already_attached: number;
  available: boolean;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}

export interface OpenVikingSyncResponse {
  available: boolean;
  synced: number;
  warning?: string | null;
  error?: {
    error_code: string;
    message: string;
  } | null;
}
