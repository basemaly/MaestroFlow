import { getBackendBaseURL } from "@/core/config";

import type {
  BrowserJobRequest,
  BrowserRuntimeConfigResponse,
  BrowserRuntimeJobResponse,
  BrowserRuntimeJobsResponse,
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
    throw new Error(body || `Browser runtime API failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getBrowserRuntimeConfig(): Promise<BrowserRuntimeConfigResponse> {
  return api("/api/browser-runtime/config");
}

export function createBrowserRuntimeJob(input: BrowserJobRequest): Promise<BrowserRuntimeJobResponse> {
  return api("/api/browser-runtime/jobs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getBrowserRuntimeJob(jobId: string): Promise<BrowserRuntimeJobResponse> {
  return api(`/api/browser-runtime/jobs/${encodeURIComponent(jobId)}`);
}

export function listBrowserRuntimeJobs(): Promise<BrowserRuntimeJobsResponse> {
  return api("/api/browser-runtime/jobs");
}
