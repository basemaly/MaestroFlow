import { getBackendBaseURL } from "@/core/config";

import type {
  DocumentRecord,
  DocumentQuickAction,
  DocumentQuickActionsListResponse,
  DocumentSnapshot,
  DocumentSnapshotsListResponse,
  DocumentsListResponse,
  DocumentTransformOperation,
} from "./types";

export async function listDocuments(): Promise<DocumentsListResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents`);
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to load documents"));
  }
  return (await response.json()) as DocumentsListResponse;
}

export async function getDocument(docId: string): Promise<DocumentRecord> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents/${encodeURIComponent(docId)}`);
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to load document"));
  }
  return (await response.json()) as DocumentRecord;
}

export async function createDocument(input: {
  title?: string;
  content_markdown: string;
  editor_json?: Record<string, unknown> | null;
  writing_memory?: string;
  status?: string;
  source_run_id?: string;
  source_version_id?: string;
  source_thread_id?: string;
  source_filepath?: string;
}): Promise<DocumentRecord> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to create document"));
  }
  return (await response.json()) as DocumentRecord;
}

export async function updateDocument(
  docId: string,
  input: {
    title?: string;
    content_markdown?: string;
    editor_json?: Record<string, unknown> | null;
    writing_memory?: string;
    status?: string;
    source_run_id?: string;
    source_version_id?: string;
    source_thread_id?: string;
    source_filepath?: string;
  },
): Promise<DocumentRecord> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents/${encodeURIComponent(docId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to save document"));
  }
  return (await response.json()) as DocumentRecord;
}

export async function transformDocumentSelection(
  docId: string,
  input: {
    document_markdown: string;
    selection_markdown: string;
    operation: DocumentTransformOperation;
    instruction?: string;
    writing_memory?: string;
    model_location?: "local" | "remote" | "mixed";
    model_strength?: "fast" | "cheap" | "strong";
    preferred_model?: string;
  },
): Promise<{ transformed_markdown: string; model_name: string }> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/documents/${encodeURIComponent(docId)}/actions/transform`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to transform selection"));
  }
  return (await response.json()) as { transformed_markdown: string; model_name: string };
}

export async function listDocumentQuickActions(): Promise<DocumentQuickActionsListResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents/quick-actions`);
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to load quick actions"));
  }
  return (await response.json()) as DocumentQuickActionsListResponse;
}

export async function createDocumentQuickAction(input: {
  name: string;
  instruction: string;
}): Promise<DocumentQuickAction> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents/quick-actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to save quick action"));
  }
  return (await response.json()) as DocumentQuickAction;
}

export async function deleteDocumentQuickAction(actionId: string): Promise<void> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents/quick-actions/${encodeURIComponent(actionId)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to delete quick action"));
  }
}

export async function listDocumentSnapshots(docId: string): Promise<DocumentSnapshotsListResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents/${encodeURIComponent(docId)}/snapshots`);
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to load snapshots"));
  }
  return (await response.json()) as DocumentSnapshotsListResponse;
}

export async function createDocumentSnapshot(
  docId: string,
  input: { label?: string; note?: string; source?: string },
): Promise<DocumentSnapshot> {
  const response = await fetch(`${getBackendBaseURL()}/api/documents/${encodeURIComponent(docId)}/snapshots`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to save snapshot"));
  }
  return (await response.json()) as DocumentSnapshot;
}

export async function restoreDocumentSnapshot(docId: string, snapshotId: string): Promise<DocumentRecord> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/documents/${encodeURIComponent(docId)}/snapshots/${encodeURIComponent(snapshotId)}/restore`,
    {
      method: "POST",
    },
  );
  if (!response.ok) {
    throw new Error(await readError(response, "Failed to restore snapshot"));
  }
  return (await response.json()) as DocumentRecord;
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallback;
  } catch {
    return fallback;
  }
}
