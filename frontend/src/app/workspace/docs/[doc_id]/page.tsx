"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";

import { BlockEditorShell } from "@/components/workspace/block-editor/block-editor-shell";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useDocument } from "@/core/documents/hooks";
import { useI18n } from "@/core/i18n/hooks";

export default function DocumentPage() {
  const { doc_id } = useParams<{ doc_id: string }>();
  const { data, isLoading, isError } = useDocument(doc_id);
  const { t } = useI18n();

  useEffect(() => {
    document.title = `${data?.title ?? t.pages.untitled} - ${t.pages.appName}`;
  }, [data?.title, t.pages.appName, t.pages.untitled]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="size-full min-h-0 p-6">
          {isLoading && !data ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Loading document...
            </div>
          ) : null}
          {!isLoading && isError ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Could not load document.
            </div>
          ) : null}
          {data ? <BlockEditorShell document={data} /> : null}
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
