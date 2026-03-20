import { apiFetch, readApiError } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";

import type {
  DiagnosticsEventEntry,
  DiagnosticsLogComponent,
  DiagnosticsLogLine,
  DiagnosticsOverview,
  DiagnosticsRequestEntry,
  DiagnosticsTraceEntry,
} from "./types";

async function api<T>(path: string): Promise<T> {
  const response = await apiFetch(`${getBackendBaseURL()}${path}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw await readApiError(response, `Diagnostics API failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getDiagnosticsOverview(): Promise<DiagnosticsOverview> {
  return api("/api/diagnostics/overview");
}

export function listDiagnosticsLogComponents(): Promise<{ components: DiagnosticsLogComponent[] }> {
  return api("/api/diagnostics/logs/components");
}

export function getDiagnosticsComponentLogs(params: {
  componentId: string;
  lines?: number;
  contains?: string;
}): Promise<{ component_id: string; path: string; exists: boolean; lines: DiagnosticsLogLine[] }> {
  const query = new URLSearchParams();
  if (params.lines) query.set("lines", String(params.lines));
  if (params.contains?.trim()) query.set("contains", params.contains.trim());
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api(`/api/diagnostics/logs/${encodeURIComponent(params.componentId)}${suffix}`);
}

export function listDiagnosticsRequests(params?: {
  limit?: number;
  pathContains?: string;
  status?: number;
  requestId?: string;
  traceId?: string;
}): Promise<{ items: DiagnosticsRequestEntry[] }> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.pathContains?.trim()) query.set("path_contains", params.pathContains.trim());
  if (params?.status) query.set("status", String(params.status));
  if (params?.requestId?.trim()) query.set("request_id", params.requestId.trim());
  if (params?.traceId?.trim()) query.set("trace_id", params.traceId.trim());
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api(`/api/diagnostics/requests${suffix}`);
}

export function listDiagnosticsTraces(params?: {
  limit?: number;
  traceId?: string;
}): Promise<{ items: DiagnosticsTraceEntry[] }> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.traceId?.trim()) query.set("trace_id", params.traceId.trim());
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api(`/api/diagnostics/traces${suffix}`);
}

export function listDiagnosticsEvents(params?: {
  limit?: number;
  kind?: "audit" | "approval";
}): Promise<{ items: DiagnosticsEventEntry[] }> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.kind) query.set("kind", params.kind);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api(`/api/diagnostics/events${suffix}`);
}
