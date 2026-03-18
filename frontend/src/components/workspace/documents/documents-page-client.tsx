"use client";

import { ArrowUpRightIcon, BookOpenTextIcon, FileTextIcon, PlusIcon, SparklesIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ExternalServiceBanner } from "@/components/workspace/external-service-banner";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useDocEditRuns } from "@/core/doc-editing/hooks";
import { useCreateDocument, useDocuments } from "@/core/documents/hooks";
import type { DocumentsListResponse } from "@/core/documents/types";
import { useI18n } from "@/core/i18n/hooks";
import { formatTimeAgo } from "@/core/utils/datetime";

export function DocumentsPageClient({
  initialDocuments,
}: {
  initialDocuments?: DocumentsListResponse;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const { data, isLoading, isError } = useDocuments(initialDocuments);
  const { data: runsData } = useDocEditRuns();
  const createDocument = useCreateDocument();
  const documents = useMemo(() => data?.documents ?? [], [data?.documents]);
  const totalWords = useMemo(
    () =>
      documents.reduce((sum, document) => {
        const count = document.content_markdown.trim().split(/\s+/).filter(Boolean).length;
        return sum + count;
      }, 0),
    [documents],
  );
  const revisionCount = runsData?.runs.length ?? 0;
  const latestRevision = runsData?.runs[0]?.timestamp
    ? formatTimeAgo(runsData.runs[0].timestamp)
    : "No revisions yet";

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
                Your main writing workspace. Draft here, revise here, and use Revision Lab only when you need side-by-side comparison.
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="outline" asChild>
                <Link href="/workspace/doc-edits">
                  <SparklesIcon className="size-4" />
                  Open Revision Lab
                </Link>
              </Button>
              <Button onClick={() => void handleCreateBlank()} disabled={createDocument.isPending}>
                <PlusIcon className="size-4" />
                New document
              </Button>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Card className="py-4">
              <CardContent className="space-y-1 px-4">
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">
                  Documents
                </div>
                <div className="text-2xl font-semibold">{documents.length}</div>
                <div className="text-muted-foreground text-sm">Persistent drafts and finished pieces</div>
              </CardContent>
            </Card>
            <Card className="py-4">
              <CardContent className="space-y-1 px-4">
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">
                  Revision Sessions
                </div>
                <div className="text-2xl font-semibold">{revisionCount}</div>
                <div className="text-muted-foreground text-sm">Latest activity {latestRevision}</div>
              </CardContent>
            </Card>
            <Card className="py-4">
              <CardContent className="space-y-1 px-4">
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">
                  Words in Play
                </div>
                <div className="text-2xl font-semibold">{totalWords.toLocaleString()}</div>
                <div className="text-muted-foreground text-sm">Across active saved documents</div>
              </CardContent>
            </Card>
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
                    <div className="flex items-start justify-between gap-3">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <FileTextIcon className="size-4" />
                        <span className="line-clamp-2">{documentRecord.title}</span>
                      </CardTitle>
                      <ArrowUpRightIcon className="size-4 shrink-0 text-muted-foreground" />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">{documentRecord.status}</Badge>
                      {documentRecord.source_run_id ? (
                        <Badge variant="secondary">From Revision Lab</Badge>
                      ) : (
                        <Badge variant="secondary">Direct draft</Badge>
                      )}
                    </div>
                    <CardDescription>
                      Updated {formatTimeAgo(documentRecord.updated_at)}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 px-4">
                    <div className="text-muted-foreground line-clamp-4 text-sm leading-6">
                      {documentRecord.content_markdown}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <BookOpenTextIcon className="size-3.5" />
                      {documentRecord.content_markdown.trim().split(/\s+/).filter(Boolean).length} words
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
