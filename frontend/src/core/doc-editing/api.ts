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
  token_budget: number;
}): Promise<DocEditRun> {
  const response = await fetch(`${getBackendBaseURL()}/api/doc-edit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to start doc edit run"));
  }
  return (await response.json()) as DocEditRun;
}

export async function selectDocEditVersion(
  runId: string,
  versionId: string,
): Promise<DocEditRun> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/doc-edit/${runId}/select/${encodeURIComponent(versionId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to select doc edit version"));
  }
  return (await response.json()) as DocEditRun;
}

export async function listDocEditRuns(): Promise<DocEditRunsResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/doc-edit/runs`);
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to load doc edit runs"));
  }
  return (await response.json()) as DocEditRunsResponse;
}

export async function getDocEditRun(runId: string): Promise<DocEditRun> {
  const response = await fetch(`${getBackendBaseURL()}/api/doc-edit/${runId}`);
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to load doc edit run"));
  }
  return (await response.json()) as DocEditRun;
}

export async function uploadDocEditFile(file: File): Promise<{ filename: string; document: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${getBackendBaseURL()}/api/doc-edit/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to upload doc edit file"));
  }
  return (await response.json()) as { filename: string; document: string };
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallback;
  } catch {
    return fallback;
  }
}
