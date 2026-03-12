"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DocEditStudio } from "@/components/workspace/doc-edit-dialog";
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
  const { data } = useDocEditRuns();
  const runs = data?.runs ?? [];

  useEffect(() => {
    document.title = `${t.sidebar.docEdits} - ${t.pages.appName}`;
  }, [t.pages.appName, t.sidebar.docEdits]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="grid size-full min-h-0 grid-cols-1 gap-6 p-6 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <div className="min-h-0">
            <Card className="h-full py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">Recent Doc Edit Runs</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 px-4">
                {runs.length === 0 && (
                  <div className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                    No doc edit runs yet.
                  </div>
                )}
                {runs.map((run) => (
                  <Link key={run.run_id} href={`/workspace/doc-edits/${run.run_id}`}>
                    <div className="rounded-lg border p-3 text-sm hover:bg-accent/40">
                      <div className="font-medium">{run.title ?? run.run_id}</div>
                      <div className="text-muted-foreground mt-1 text-xs">
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
