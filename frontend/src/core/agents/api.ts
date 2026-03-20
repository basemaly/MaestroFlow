import { apiFetch, readApiError } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";

import type { Agent, CreateAgentRequest, UpdateAgentRequest } from "./types";

export async function listAgents(): Promise<Agent[]> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents`);
  if (!res.ok) throw await readApiError(res, "Failed to load agents");
  const data = (await res.json()) as { agents: Agent[] };
  return data.agents;
}

export async function getAgent(name: string): Promise<Agent> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${name}`);
  if (!res.ok) throw await readApiError(res, `Agent '${name}' not found`);
  return res.json() as Promise<Agent>;
}

export async function createAgent(request: CreateAgentRequest): Promise<Agent> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw await readApiError(res, "Failed to create agent");
  }
  return res.json() as Promise<Agent>;
}

export async function updateAgent(
  name: string,
  request: UpdateAgentRequest,
): Promise<Agent> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw await readApiError(res, "Failed to update agent");
  }
  return res.json() as Promise<Agent>;
}

export async function deleteAgent(name: string): Promise<void> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${name}`, {
    method: "DELETE",
  });
  if (!res.ok) throw await readApiError(res, "Failed to delete agent");
}

export async function checkAgentName(
  name: string,
): Promise<{ available: boolean; name: string }> {
  const res = await apiFetch(
    `${getBackendBaseURL()}/api/agents/check?name=${encodeURIComponent(name)}`,
  );
  if (!res.ok) {
    throw await readApiError(res, "Failed to check agent name");
  }
  return res.json() as Promise<{ available: boolean; name: string }>;
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

export async function getAgentMemory(name: string): Promise<{ content: string }> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/memory`);
  if (!res.ok) throw await readApiError(res, "Failed to load agent memory");
  return res.json() as Promise<{ content: string }>;
}

export async function updateAgentMemory(name: string, content: string): Promise<{ content: string }> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/memory`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw await readApiError(res, "Failed to save agent memory");
  return res.json() as Promise<{ content: string }>;
}

export async function clearAgentMemory(name: string): Promise<void> {
  await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/memory`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

export async function getAgentTools(name: string): Promise<{ allowed_tools: string[] }> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/tools`);
  if (!res.ok) throw await readApiError(res, "Failed to load agent tools");
  return res.json() as Promise<{ allowed_tools: string[] }>;
}

export async function updateAgentTools(name: string, allowed_tools: string[]): Promise<{ allowed_tools: string[] }> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/tools`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ allowed_tools }),
  });
  if (!res.ok) throw await readApiError(res, "Failed to update agent tools");
  return res.json() as Promise<{ allowed_tools: string[] }>;
}

// ---------------------------------------------------------------------------
// Schedules
// ---------------------------------------------------------------------------

export interface AgentSchedule {
  schedule_id: string;
  agent_name: string;
  cron_expr: string;
  prompt: string;
  enabled: boolean;
  last_run: string | null;
  next_run: string | null;
  last_thread_id: string | null;
  created_at: string;
}

export async function listAgentSchedules(name: string): Promise<AgentSchedule[]> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/schedules`);
  if (!res.ok) throw await readApiError(res, "Failed to list schedules");
  return res.json() as Promise<AgentSchedule[]>;
}

export async function createAgentSchedule(name: string, data: { cron_expr: string; prompt: string; enabled?: boolean }): Promise<AgentSchedule> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/schedules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await readApiError(res, "Failed to create schedule");
  return res.json() as Promise<AgentSchedule>;
}

export async function updateAgentSchedule(name: string, scheduleId: string, data: { enabled?: boolean; cron_expr?: string; prompt?: string }): Promise<AgentSchedule> {
  const res = await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/schedules/${scheduleId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw await readApiError(res, "Failed to update schedule");
  return res.json() as Promise<AgentSchedule>;
}

export async function deleteAgentSchedule(name: string, scheduleId: string): Promise<void> {
  await apiFetch(`${getBackendBaseURL()}/api/agents/${encodeURIComponent(name)}/schedules/${scheduleId}`, { method: "DELETE" });
}
