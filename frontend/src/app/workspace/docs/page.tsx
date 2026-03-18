import { DocumentsPageClient } from "@/components/workspace/documents/documents-page-client";
import type { DocumentsListResponse } from "@/core/documents/types";
import { getServerAppOrigin } from "@/core/server/app-origin";

async function loadInitialDocuments(): Promise<DocumentsListResponse> {
  try {
    const origin = await getServerAppOrigin();
    const response = await fetch(`${origin}/api/documents`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return { documents: [] };
    }
    return (await response.json()) as DocumentsListResponse;
  } catch {
    return { documents: [] };
  }
}

export default async function DocumentsPage() {
  const initialDocuments = await loadInitialDocuments();
  return <DocumentsPageClient initialDocuments={initialDocuments} />;
}
