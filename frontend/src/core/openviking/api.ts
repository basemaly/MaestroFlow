import { getBackendBaseURL } from "@/core/config";

import type {
  OpenVikingAttachResponse,
  OpenVikingConfigResponse,
  OpenVikingContextPack,
  OpenVikingSearchResponse,
  OpenVikingSyncResponse,
} from "./types";

function normalizePack(pack: Record<string, unknown>): OpenVikingContextPack {
  const sourceMetadata =
    typeof pack.source_metadata === "object" && pack.source_metadata
      ? (pack.source_metadata as Record<string, unknown>)
      : {};
  const packId = typeof pack.pack_id === "string" ? pack.pack_id : "";
  const title = typeof pack.title === "string" ? pack.title : packId || "Untitled pack";
  const description = typeof pack.description === "string" ? pack.description : "";
  return {
    pack_id: packId,
    title,
    description,
    references: Array.isArray(pack.references) ? pack.references.map(String) : [],
    skills: Array.isArray(pack.skills) ? pack.skills.map(String) : [],
    prompts: Array.isArray(pack.prompts) ? pack.prompts.map(String) : [],
    source:
      typeof pack.source === "string"
        ? pack.source
        : typeof sourceMetadata.source === "string"
          ? String(sourceMetadata.source)
          : null,
    metadata:
      typeof pack.metadata === "object" && pack.metadata
        ? (pack.metadata as Record<string, unknown>)
        : sourceMetadata,
  };
}

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
    throw new Error(body || `OpenViking API failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getOpenVikingConfig(): Promise<OpenVikingConfigResponse> {
  return api("/api/openviking/config");
}

export function searchOpenVikingContextPacks(input: {
  query?: string;
  top_k?: number;
  source_key?: string;
}): Promise<OpenVikingSearchResponse> {
  return api<{ items: Record<string, unknown>[]; available?: boolean; warning?: string | null; error?: OpenVikingSearchResponse["error"] }>("/api/openviking/packs/search", {
    method: "POST",
    body: JSON.stringify(input),
  }).then((payload) => ({
    items: (payload.items ?? []).map(normalizePack),
    available: payload.available ?? true,
    warning: payload.warning ?? null,
    error: payload.error ?? null,
  }));
}

export function attachOpenVikingContextPacks(input: {
  packs: OpenVikingContextPack[];
  scope?: string;
  project_key?: string;
}): Promise<OpenVikingAttachResponse> {
  return api<{ items: Record<string, unknown>[]; attached: number; already_attached: number; available?: boolean; warning?: string | null; error?: OpenVikingAttachResponse["error"] }>("/api/openviking/packs/attach", {
    method: "POST",
    body: JSON.stringify(input),
  }).then((payload) => ({
    items: (payload.items ?? []).map(normalizePack),
    attached: payload.attached,
    already_attached: payload.already_attached,
    available: payload.available ?? true,
    warning: payload.warning ?? null,
    error: payload.error ?? null,
  }));
}

export function detachOpenVikingContextPack(input: {
  pack_id: string;
  scope?: string;
  project_key?: string;
}): Promise<OpenVikingAttachResponse> {
  return api("/api/openviking/packs/detach", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function syncOpenVikingContextPacks(input?: {
  scope?: string;
  project_key?: string;
}): Promise<OpenVikingSyncResponse> {
  return api("/api/openviking/packs/sync", {
    method: "POST",
    body: JSON.stringify(input ?? {}),
  });
}
