"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";

import { BlockEditorShell } from "@/components/workspace/block-editor/block-editor-shell";
import { ContextDock } from "@/components/workspace/context-dock";
import { DocEditDialog } from "@/components/workspace/doc-edit-dialog";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useDocument } from "@/core/documents/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { useLocalSettings } from "@/core/settings";

export default function DocumentPage() {
  const { doc_id } = useParams<{ doc_id: string }>();
  const { data, isLoading, isError } = useDocument(doc_id);
  const { t } = useI18n();
  const [settings, setSettings] = useLocalSettings();

  useEffect(() => {
    document.title = `${data?.title ?? t.pages.untitled} - ${t.pages.appName}`;
  }, [data?.title, t.pages.appName, t.pages.untitled]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="size-full min-h-0 p-6">
          <div className="mb-4">
            <ContextDock
              knowledgeSource={
                (settings.context.knowledge_source as "auto" | "calibre-library" | undefined) ??
                "auto"
              }
              onKnowledgeSourceChange={(knowledge_source) =>
                setSettings("context", { knowledge_source })
              }
              agentPreset={
                typeof settings.context.agent_name === "string"
                  ? settings.context.agent_name
                  : undefined
              }
              onAgentPresetChange={(agent_name) =>
                setSettings("context", { agent_name })
              }
              mode={settings.context.mode}
              includeRevisionLab
            />
          </div>
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
          <DocEditDialog
            disabled={false}
            mode={settings.context.mode}
            showTrigger={false}
          />
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
