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
  const latestRevisionRun = runsData?.runs[0];
  const latestRevision = runsData?.runs[0]?.timestamp
    ? formatTimeAgo(runsData.runs[0].timestamp)
    : "No revision sessions yet";

  useEffect(() => {
    document.title = `${t.sidebar.documents} - ${t.pages.appName}`;
  }, [t.pages.appName, t.sidebar.documents]);

  async function handleCreateBlank() {
    try {
      const documentRecord = await createDocument.mutateAsync({
        title: "Untitled piece",
        content_markdown: "# Untitled piece\n\nStart composing here.",
        status: "draft",
      });
      void router.push(`/workspace/composer/${documentRecord.doc_id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : String(error));
    }
  }

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <ExternalServiceBanner />
        <div className="size-full space-y-6 bg-[radial-gradient(circle_at_top_left,rgba(217,119,6,0.08),transparent_22%),radial-gradient(circle_at_top_right,rgba(20,83,45,0.08),transparent_20%)] p-6">
          <div className="rounded-3xl border border-border/70 bg-background/85 p-5 shadow-sm backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">Composer Desk</div>
                <div className="text-2xl font-semibold tracking-tight">{t.sidebar.documents}</div>
                <div className="max-w-2xl text-sm text-muted-foreground">
                Draft at the desk, move fragments into Collage when the piece gets unwieldy, and use Revision Lab when you need competing versions side by side.
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {latestRevisionRun ? (
                  <Button variant="ghost" asChild>
                    <Link href={`/workspace/doc-edits/${latestRevisionRun.run_id}`}>
                      <ArrowUpRightIcon className="size-4" />
                      Resume latest revision
                    </Link>
                  </Button>
                ) : null}
                <Button variant="outline" asChild>
                  <Link href="/workspace/doc-edits">
                    <SparklesIcon className="size-4" />
                    Open Revision Lab
                  </Link>
                </Button>
                <Button onClick={() => void handleCreateBlank()} disabled={createDocument.isPending}>
                  <PlusIcon className="size-4" />
                  New piece
                </Button>
              </div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <Card className="border-border/70 bg-background/85 py-4 shadow-sm">
              <CardContent className="space-y-1 px-4">
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">
                  Composer Pieces
                </div>
                <div className="text-2xl font-semibold">{documents.length}</div>
                <div className="text-muted-foreground text-sm">Persistent drafts and finished pieces</div>
              </CardContent>
            </Card>
            <Card className="border-border/70 bg-background/85 py-4 shadow-sm">
              <CardContent className="space-y-1 px-4">
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">
                  Revision Sessions
                </div>
                <div className="text-2xl font-semibold">{revisionCount}</div>
                <div className="text-muted-foreground text-sm">Latest activity {latestRevision}</div>
              </CardContent>
            </Card>
            <Card className="border-border/70 bg-background/85 py-4 shadow-sm">
              <CardContent className="space-y-1 px-4">
                <div className="text-muted-foreground text-xs uppercase tracking-[0.16em]">
                  Words in Play
                </div>
                <div className="text-2xl font-semibold">{totalWords.toLocaleString()}</div>
                <div className="text-muted-foreground text-sm">Across active saved drafts</div>
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
                  Could not load Composer.
                </CardContent>
              </Card>
            )}
            {!isLoading && !isError && documents.length === 0 && (
              <Card className="py-4">
                <CardContent className="text-muted-foreground px-4 text-sm">
                  No drafts yet.
                </CardContent>
              </Card>
            )}
            {!isLoading && !isError && documents.map((documentRecord) => (
              <Link key={documentRecord.doc_id} href={`/workspace/composer/${documentRecord.doc_id}`}>
                <Card className="h-full gap-4 border-border/70 bg-background/88 py-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-amber-500/30 hover:bg-accent/30">
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
