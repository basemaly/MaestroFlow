import { getBackendBaseURL } from "@/core/config";

import type {
  CalibreBook,
  CalibreBrowseMetadata,
  CalibreQueryResponse,
  CalibreStatusResponse,
} from "./types";

export async function getCalibreStatus(
  collection?: string
): Promise<CalibreStatusResponse> {
  const params = new URLSearchParams();
  if (collection) params.append("collection", collection);

  const response = await fetch(
    `${getBackendBaseURL()}/api/calibre/status${params.size > 0 ? `?${params}` : ""}`,
    {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(`Calibre status failed: ${response.statusText}`);
  }

  return response.json();
}

export async function queryCalibre(input: {
  query: string;
  top_k?: number;
  filters?: Record<string, unknown>;
  collection?: string;
}): Promise<CalibreQueryResponse> {
  const body: Record<string, unknown> = {
    query: input.query.trim() || "*",
    top_k: input.top_k ?? 8,
  };

  if (input.filters) {
    body.filters = input.filters;
  }
  if (input.collection) {
    body.collection = input.collection;
  }

  const response = await fetch(
    `${getBackendBaseURL()}/api/calibre/query`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    const bodyText = await response.text().catch(() => "");
    throw new Error(bodyText || `Calibre query failed: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

export async function syncCalibre(input: {
  full?: boolean;
  collection?: string;
}): Promise<CalibreStatusResponse> {
  const params = new URLSearchParams();
  if (input.full) params.append("full", "true");
  if (input.collection) params.append("collection", input.collection);

  const response = await fetch(
    `${getBackendBaseURL()}/api/calibre/sync${params.size > 0 ? `?${params}` : ""}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(`Calibre sync failed: ${response.statusText}`);
  }

  return response.json();
}

export async function reindexCalibre(input: {
  collection?: string;
}): Promise<CalibreStatusResponse> {
  const params = new URLSearchParams();
  if (input.collection) params.append("collection", input.collection);

  const response = await fetch(
    `${getBackendBaseURL()}/api/calibre/reindex${params.size > 0 ? `?${params}` : ""}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(`Calibre reindex failed: ${response.statusText}`);
  }

  return response.json();
}

export function extractBrowseMetadata(books: CalibreBook[]): CalibreBrowseMetadata {
  const authors = new Set<string>();
  const tags = new Set<string>();
  const series = new Set<string>();

  for (const book of books) {
    if (book.authors) {
      book.authors.forEach(a => authors.add(a));
    }
    if (book.tags) {
      book.tags.forEach(t => tags.add(t));
    }
    if (book.series) {
      series.add(book.series);
    }
  }

  return {
    authors: Array.from(authors).sort(),
    tags: Array.from(tags).sort(),
    series: Array.from(series).sort(),
  };
}
