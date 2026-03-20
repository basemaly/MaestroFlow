import { apiFetch } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";

import type {
  ActivepiecesConfigResponse,
  ActivepiecesFlowPreviewResponse,
  ActivepiecesFlowTriggerResponse,
  ActivepiecesFlowsResponse,
  ActivepiecesWebhookResponse,
} from "./types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiFetch(`${getBackendBaseURL()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(body || `Activepieces API failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getActivepiecesConfig(): Promise<ActivepiecesConfigResponse> {
  return api("/api/activepieces/config");
}

export function listActivepiecesFlows(): Promise<ActivepiecesFlowsResponse> {
  return api<{ flows: Array<Record<string, unknown>>; available?: boolean; warning?: string | null; error?: ActivepiecesFlowsResponse["error"] }>("/api/activepieces/flows").then((payload) => ({
    flows: (payload.flows ?? []).map((flow) => ({
      flow_id: typeof flow.flow_id === "string" ? flow.flow_id : "",
      label:
        typeof flow.label === "string"
          ? flow.label
          : typeof flow.flow_id === "string"
            ? flow.flow_id
            : "Untitled flow",
      description: typeof flow.description === "string" ? flow.description : "",
      component_scope: Array.isArray(flow.component_scope) ? flow.component_scope.map(String) : [],
      approval_required: Boolean(flow.approval_required ?? flow.requires_approval),
      input_contract:
        typeof flow.input_contract === "object" && flow.input_contract
          ? (flow.input_contract as Record<string, unknown>)
          : typeof flow.input_schema === "object" && flow.input_schema
            ? (flow.input_schema as Record<string, unknown>)
            : {},
      enabled: true,
      metadata: typeof flow.metadata === "object" && flow.metadata ? (flow.metadata as Record<string, unknown>) : {},
    })),
    available: payload.available ?? true,
    warning: payload.warning ?? null,
    error: payload.error ?? null,
  }));
}

export function previewActivepiecesFlow(flowId: string, input: Record<string, unknown>): Promise<ActivepiecesFlowPreviewResponse> {
  return api(`/api/activepieces/flows/${encodeURIComponent(flowId)}/preview`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

export function triggerActivepiecesFlow(flowId: string, input: Record<string, unknown>): Promise<ActivepiecesFlowTriggerResponse> {
  return api(`/api/activepieces/flows/${encodeURIComponent(flowId)}/trigger`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

export function receiveActivepiecesWebhook(webhookKey: string, input: Record<string, unknown>): Promise<ActivepiecesWebhookResponse> {
  return api(`/api/activepieces/webhooks/${encodeURIComponent(webhookKey)}`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}
