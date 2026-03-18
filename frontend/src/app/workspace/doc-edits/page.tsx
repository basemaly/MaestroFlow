"use client";

import { ArrowRightIcon, BookOpenTextIcon, SparklesIcon } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DocEditStudio } from "@/components/workspace/doc-edit-dialog";
import { ExternalServiceBanner } from "@/components/workspace/external-service-banner";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useDocEditRuns } from "@/core/doc-editing/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { useLocalSettings } from "@/core/settings";
import { formatTimeAgo } from "@/core/utils/datetime";

export default function DocEditsPage() {
  const { t } = useI18n();
  const [settings] = useLocalSettings();
  const { data, isLoading, isError } = useDocEditRuns();
  const runs = data?.runs ?? [];

  useEffect(() => {
    document.title = `${t.sidebar.docEdits} - ${t.pages.appName}`;
  }, [t.pages.appName, t.sidebar.docEdits]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <ExternalServiceBanner />
        <div className="grid size-full min-h-0 grid-cols-1 gap-6 p-6 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <div className="min-h-0">
            <Card className="h-full py-4">
              <CardHeader className="px-4">
                <div className="space-y-3">
                  <div className="space-y-1">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <SparklesIcon className="size-4" />
                      {t.sidebar.docEdits}
                    </CardTitle>
                    <div className="text-muted-foreground text-sm">
                      Use this for heavier compare-and-choose sessions. For normal drafting, stay in Documents and open Revision Lab only when needed.
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="outline">{runs.length} runs</Badge>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/workspace/docs">
                        <BookOpenTextIcon className="size-4" />
                        Back to Documents
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 px-4">
                {isLoading && (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <div
                        key={`doc-edit-skeleton-${index}`}
                        className="h-[4.5rem] animate-pulse rounded-lg border bg-muted/30"
                      />
                    ))}
                  </div>
                )}
                {!isLoading && isError && (
                  <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                    Could not load recent doc edit runs.
                  </div>
                )}
                {!isLoading && !isError && runs.length === 0 && (
                  <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                    No doc edit runs yet.
                  </div>
                )}
                {!isLoading && !isError && runs.map((run) => (
                  <Link key={run.run_id} href={`/workspace/doc-edits/${run.run_id}`}>
                    <div className="rounded-xl border p-3 text-sm transition-colors hover:bg-accent/40">
                      <div className="flex items-start justify-between gap-3">
                        <div className="font-medium">{run.title ?? run.run_id}</div>
                        <ArrowRightIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                      </div>
                      <div className="text-muted-foreground mt-2 text-xs">
                        {run.status} · {run.timestamp ? formatTimeAgo(run.timestamp) : "Unknown time"}
                      </div>
                      <div className="text-muted-foreground mt-1 text-xs">
                        {run.skills_used?.join(", ") ?? "No skills recorded"}
                      </div>
                    </div>
                  </Link>
                ))}
              </CardContent>
            </Card>
          </div>
          <div className="min-h-0">
            <DocEditStudio mode={settings.context.mode} embedded />
          </div>
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
