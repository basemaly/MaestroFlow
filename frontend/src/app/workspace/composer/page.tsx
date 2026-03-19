import { DocumentsPageClient } from "@/components/workspace/documents/documents-page-client";
import type { DocumentsListResponse } from "@/core/documents/types";
import { getServerAppOrigin } from "@/core/server/app-origin";

async function loadInitialDocuments(): Promise<DocumentsListResponse> {
  try {
    const origin = await getServerAppOrigin();
    const response = await fetch(`${origin}/api/documents`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) {
      return { documents: [] };
    }
    return (await response.json()) as DocumentsListResponse;
  } catch {
    return { documents: [] };
  }
}

export default async function ComposerPage() {
  const initialDocuments = await loadInitialDocuments();
  return <DocumentsPageClient initialDocuments={initialDocuments} />;
}
