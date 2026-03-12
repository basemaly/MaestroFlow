"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";

import { DocEditStudio } from "@/components/workspace/doc-edit-dialog";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useDocEditRun } from "@/core/doc-editing/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { useLocalSettings } from "@/core/settings";

export default function DocEditRunPage() {
  const { run_id } = useParams<{ run_id: string }>();
  const { t } = useI18n();
  const [settings] = useLocalSettings();
  const { data, isLoading } = useDocEditRun(run_id);

  useEffect(() => {
    document.title = `${data?.title ?? run_id} - ${t.sidebar.docEdits} - ${t.pages.appName}`;
  }, [data?.title, run_id, t.pages.appName, t.sidebar.docEdits]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="size-full min-h-0 p-6">
          {isLoading && !data ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Loading doc edit run...
            </div>
          ) : (
            <DocEditStudio
              embedded
              mode={settings.context.mode}
              initialRun={data}
            />
          )}
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
