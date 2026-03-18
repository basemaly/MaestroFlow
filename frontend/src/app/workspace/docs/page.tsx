"use client";

import { FileTextIcon, PlusIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ExternalServiceBanner } from "@/components/workspace/external-service-banner";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useCreateDocument, useDocuments } from "@/core/documents/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { formatTimeAgo } from "@/core/utils/datetime";

export default function DocumentsPage() {
  const router = useRouter();
  const { t } = useI18n();
  const { data, isLoading, isError } = useDocuments();
  const createDocument = useCreateDocument();
  const documents = data?.documents ?? [];

  useEffect(() => {
    document.title = `${t.sidebar.documents} - ${t.pages.appName}`;
  }, [t.pages.appName, t.sidebar.documents]);

  async function handleCreateBlank() {
    try {
      const documentRecord = await createDocument.mutateAsync({
        title: "Untitled document",
        content_markdown: "# Untitled document\n\nStart writing here.",
        status: "draft",
      });
      void router.push(`/workspace/docs/${documentRecord.doc_id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <ExternalServiceBanner />
        <div className="size-full space-y-6 p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-2xl font-semibold">{t.sidebar.documents}</div>
              <div className="text-muted-foreground text-sm">
                Persistent editable documents with AI-assisted refinement.
              </div>
            </div>
            <Button onClick={() => void handleCreateBlank()} disabled={createDocument.isPending}>
              <PlusIcon className="size-4" />
              New document
            </Button>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {isLoading && Array.from({ length: 6 }).map((_, index) => (
              <div
                key={`document-skeleton-${index}`}
                className="h-44 animate-pulse rounded-xl border bg-muted/25"
              />
            ))}
            {!isLoading && isError && (
              <Card className="py-4">
                <CardContent className="text-muted-foreground px-4 text-sm">
                  Could not load documents.
                </CardContent>
              </Card>
            )}
            {!isLoading && !isError && documents.length === 0 && (
              <Card className="py-4">
                <CardContent className="text-muted-foreground px-4 text-sm">
                  No documents yet.
                </CardContent>
              </Card>
            )}
            {!isLoading && !isError && documents.map((documentRecord) => (
              <Link key={documentRecord.doc_id} href={`/workspace/docs/${documentRecord.doc_id}`}>
                <Card className="h-full gap-4 py-4 transition-colors hover:bg-accent/40">
                  <CardHeader className="px-4">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <FileTextIcon className="size-4" />
                      {documentRecord.title}
                    </CardTitle>
                    <CardDescription>
                      {documentRecord.status} · Updated {formatTimeAgo(documentRecord.updated_at)}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="px-4">
                    <div className="text-muted-foreground line-clamp-4 text-sm leading-6">
                      {documentRecord.content_markdown}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
