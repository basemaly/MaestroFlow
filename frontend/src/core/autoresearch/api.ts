import type {
  AutoresearchExperimentDetail,
  AutoresearchRegistryPayload,
  ExperimentSummary,
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
    throw new Error(body || `Autoresearch API failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getAutoresearchRegistry(): Promise<AutoresearchRegistryPayload> {
  return api("/api/autoresearch/registry");
}

export function listAutoresearchExperiments(): Promise<{ experiments: ExperimentSummary[] }> {
  return api("/api/autoresearch/experiments");
}

export function getAutoresearchExperiment(experimentId: string): Promise<AutoresearchExperimentDetail> {
  return api(`/api/autoresearch/experiments/${encodeURIComponent(experimentId)}`);
}

export function createPromptExperiment(input: {
  role: string;
  title?: string;
  notes?: string;
  max_mutations?: number;
  benchmark_limit?: number;
}): Promise<AutoresearchExperimentDetail> {
  return api("/api/autoresearch/experiments/prompt", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createUiDesignExperiment(input: {
  prompt: string;
  component_code: string;
  title?: string;
  max_iterations?: number;
}): Promise<AutoresearchExperimentDetail> {
  return api("/api/autoresearch/experiments/ui-design", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createWorkflowRouteExperiment(input: {
  template_id: string;
  title?: string;
  max_mutations?: number;
}): Promise<AutoresearchExperimentDetail> {
  return api("/api/autoresearch/experiments/workflow-route", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function approveAutoresearchExperiment(experimentId: string): Promise<AutoresearchExperimentDetail> {
  return api(`/api/executive/autoresearch/experiments/${encodeURIComponent(experimentId)}/approve`, {
    method: "POST",
  });
}

export function rejectAutoresearchExperiment(
  experimentId: string,
  reason?: string,
): Promise<AutoresearchExperimentDetail> {
  return api(`/api/executive/autoresearch/experiments/${encodeURIComponent(experimentId)}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? "" }),
  });
}

export function stopAutoresearchExperiment(
  experimentId: string,
  reason?: string,
): Promise<AutoresearchExperimentDetail> {
  return api(`/api/executive/autoresearch/experiments/${encodeURIComponent(experimentId)}/stop`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? "" }),
  });
}
