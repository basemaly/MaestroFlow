import type {
  ExecutiveActionPreview,
  ExecutiveActionDefinition,
  ExecutiveAdvisoryRule,
  ExecutiveApprovalRequest,
  ExecutiveAuditEntry,
  ExecutiveComponent,
  ExecutiveExecutionResult,
  ExecutiveSystemStatus,
} from "./types";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Executive API failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getExecutiveRegistry(): Promise<{
  components: ExecutiveComponent[];
  actions: ExecutiveActionDefinition[];
}> {
  return api("/api/executive/registry");
}

export function getExecutiveStatus(): Promise<ExecutiveSystemStatus> {
  return api("/api/executive/status");
}

export function getExecutiveAdvisory(): Promise<{ rules: ExecutiveAdvisoryRule[] }> {
  return api("/api/executive/advisory");
}

export function getExecutiveApprovals(): Promise<{ approvals: ExecutiveApprovalRequest[] }> {
  return api("/api/executive/approvals");
}

export function getExecutiveAudit(): Promise<{ entries: ExecutiveAuditEntry[] }> {
  return api("/api/executive/audit");
}

export function previewExecutiveAction(body: {
  action_id: string;
  component_id: string;
  input: Record<string, unknown>;
  requested_by?: string;
}): Promise<ExecutiveActionPreview> {
  return api("/api/executive/actions/preview", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function executeExecutiveAction(body: {
  action_id: string;
  component_id: string;
  input: Record<string, unknown>;
  requested_by?: string;
}): Promise<ExecutiveExecutionResult> {
  return api("/api/executive/actions/execute", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function confirmExecutiveApproval(approvalId: string): Promise<ExecutiveExecutionResult> {
  return api(`/api/executive/approvals/${approvalId}/confirm`, { method: "POST" });
}

export function rejectExecutiveApproval(approvalId: string): Promise<ExecutiveExecutionResult> {
  return api(`/api/executive/approvals/${approvalId}/reject`, { method: "POST" });
}

export function getExecutiveSettings(): Promise<{ model: string; available_models: string[] }> {
  return api("/api/executive/settings");
}

export function updateExecutiveSettings(model: string): Promise<{ model: string; available_models: string[] }> {
  return api("/api/executive/settings", {
    method: "PUT",
    body: JSON.stringify({ model }),
  });
}

export function executiveChat(
  messages: Array<{ role: "user" | "assistant" | "system"; content: string }>,
  signal?: AbortSignal,
): Promise<{
  answer: string;
  recommendations: Array<{ title: string; summary: string; action_id?: string | null; component_id?: string | null; priority: number }>;
}> {
  return api("/api/executive/chat", {
    method: "POST",
    signal,
    body: JSON.stringify({ messages }),
  });
}
