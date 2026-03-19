import type { BrowserRuntimeChoice } from "@/core/browser-runtime";

import type {
  AutoresearchExperimentDetail,
  AutoresearchRegistryPayload,
  ExperimentSummary,
} from "./types";

const REQUEST_TIMEOUT_MS = 30_000;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
    if (!response.ok) {
      let message: string;
      try {
        const body = await response.json();
        message = typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
      } catch {
        message = await response.text().catch(() => "");
      }
      throw new Error(message || `Request failed (${response.status})`);
    }
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timed out. The operation may still be running in the background.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
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
  browser_runtime?: BrowserRuntimeChoice;
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
