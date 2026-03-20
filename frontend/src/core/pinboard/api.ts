import { apiFetch } from "@/core/api/fetch";
import { getBackendBaseURL } from "@/core/config";

import type {
  PinboardBookmark,
  PinboardConfigResponse,
  PinboardImportResponse,
  PinboardPreviewImportResponse,
  PinboardSearchResponse,
} from "./types";

export async function getPinboardConfig(): Promise<PinboardConfigResponse> {
  const response = await apiFetch(`${getBackendBaseURL()}/api/pinboard/config`, { cache: "no-store" });
  return (await response.json()) as PinboardConfigResponse;
}

export async function searchPinboardBookmarks(input: {
  query?: string;
  tag?: string;
  top_k?: number;
}): Promise<PinboardSearchResponse> {
  const response = await apiFetch(`${getBackendBaseURL()}/api/pinboard/bookmarks/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return (await response.json()) as PinboardSearchResponse;
}

export async function previewPinboardImport(input: {
  query?: string;
  tag?: string;
  top_k?: number;
  project_key?: string;
  search_space_id?: number;
}): Promise<PinboardPreviewImportResponse> {
  const response = await apiFetch(`${getBackendBaseURL()}/api/pinboard/bookmarks/preview-import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return (await response.json()) as PinboardPreviewImportResponse;
}

export async function importPinboardBookmarks(input: {
  bookmarks: PinboardBookmark[];
  project_key?: string;
  search_space_id?: number;
}): Promise<PinboardImportResponse> {
  const response = await apiFetch(`${getBackendBaseURL()}/api/pinboard/bookmarks/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return (await response.json()) as PinboardImportResponse;
}
