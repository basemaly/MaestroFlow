import { getBackendBaseURL } from "@/core/config";

import type {
  StateConfigResponse,
  StateDiffResponse,
  StateExportResponse,
  StateSnapshot,
  StateSnapshotsResponse,
  StateSnapshotFormat,
  StateScope,
} from "./types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getBackendBaseURL()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(body || `State API failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getStateConfig(): Promise<StateConfigResponse> {
  return api("/api/state/config");
}

export function listStateSnapshots(input?: {
  scope?: StateScope;
  reference_id?: string;
  state_type?: string;
  limit?: number;
}): Promise<StateSnapshotsResponse> {
  const query = new URLSearchParams();
  if (input?.scope) query.set("scope", input.scope);
  if (input?.reference_id) query.set("reference_id", input.reference_id);
  if (input?.state_type) query.set("state_type", input.state_type);
  if (typeof input?.limit === "number") query.set("limit", String(input.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return api(`/api/state/snapshots${suffix}`);
}

export function createStateSnapshot(input: {
  scope: StateScope;
  reference_id?: string;
  label: string;
  summary?: string;
  data?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}): Promise<{ available: boolean; snapshot: StateSnapshot; warning?: string | null; error?: { error_code: string; message: string } | null }> {
  return api("/api/state/snapshots", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getStateSnapshot(snapshotId: string): Promise<{ available: boolean; snapshot: StateSnapshot; warning?: string | null; error?: { error_code: string; message: string } | null }> {
  return api(`/api/state/snapshots/${encodeURIComponent(snapshotId)}`);
}

export function diffStateSnapshots(input: {
  left_snapshot_id: string;
  right_snapshot_id: string;
}): Promise<StateDiffResponse> {
  return api("/api/state/diff", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function exportStateSnapshot(input: {
  snapshot_id: string;
  export_format?: StateSnapshotFormat;
}): Promise<StateExportResponse> {
  return api("/api/state/export", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      export_format: input.export_format ?? "json",
    }),
  });
}
