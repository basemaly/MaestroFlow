import { apiFetch, buildTraceId, readApiError } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";

import type { DocEditRun, DocEditRunsResponse } from "./types";

export async function startDocEditRun(input: {
  document: string;
  skills: string[];
  workflow_mode: "standard" | "consensus" | "debate-judge" | "critic-loop" | "strict-bold";
  model_location: "local" | "remote" | "mixed";
  model_strength: "fast" | "cheap" | "strong";
  preferred_model?: string;
  selected_models?: string[];
  project_key?: string;
  surfsense_search_space_id?: number;
  token_budget: number;
}): Promise<DocEditRun> {
  const response = await apiFetch(`${getBackendBaseURL()}/api/doc-edit`, {
    method: "POST",
    traceId: buildTraceId("doc-edit-run"),
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw await readApiError(response, "Failed to start doc edit run");
  }
  return (await response.json()) as DocEditRun;
}

export async function selectDocEditVersion(
  runId: string,
  versionId: string,
): Promise<DocEditRun> {
  const response = await apiFetch(
    `${getBackendBaseURL()}/api/doc-edit/${runId}/select/${encodeURIComponent(versionId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
    },
  );
  if (!response.ok) {
    throw await readApiError(response, "Failed to select doc edit version");
  }
  return (await response.json()) as DocEditRun;
}

export async function listDocEditRuns(): Promise<DocEditRunsResponse> {
  const response = await apiFetch(`${getBackendBaseURL()}/api/doc-edit/runs`);
  if (!response.ok) {
    throw await readApiError(response, "Failed to load doc edit runs");
  }
  return (await response.json()) as DocEditRunsResponse;
}

export async function getDocEditRun(runId: string): Promise<DocEditRun> {
  const response = await apiFetch(`${getBackendBaseURL()}/api/doc-edit/${runId}`);
  if (!response.ok) {
    throw await readApiError(response, "Failed to load doc edit run");
  }
  return (await response.json()) as DocEditRun;
}

export async function uploadDocEditFile(file: File): Promise<{ filename: string; document: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch(`${getBackendBaseURL()}/api/doc-edit/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw await readApiError(response, "Failed to upload doc edit file");
  }
  return (await response.json()) as { filename: string; document: string };
}
