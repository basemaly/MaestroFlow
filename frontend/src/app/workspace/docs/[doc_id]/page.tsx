"use client";

import { BookOpenTextIcon, LayoutPanelTopIcon } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { BlockEditorShell } from "@/components/workspace/block-editor/block-editor-shell";
import { CollageWorkspace } from "@/components/workspace/collage/collage-workspace";
import { ContextDock } from "@/components/workspace/context-dock";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { Button } from "@/components/ui/button";
import { useDocument } from "@/core/documents/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { useLocalSettings } from "@/core/settings";

export default function DocumentPage() {
  const { doc_id } = useParams<{ doc_id: string }>();
  const { data, isLoading, isError } = useDocument(doc_id);
  const { t } = useI18n();
  const [settings, setSettings] = useLocalSettings();
  const [viewMode, setViewMode] = useState<"editor" | "collage">("editor");

  useEffect(() => {
    document.title = `${data?.title ?? t.pages.untitled} - ${t.pages.appName}`;
  }, [data?.title, t.pages.appName, t.pages.untitled]);

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="size-full min-h-0 p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
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
            <div className="flex items-center gap-1 rounded-lg border p-0.5 shrink-0">
              <Button
                size="sm"
                variant={viewMode === "editor" ? "default" : "ghost"}
                className="h-7 gap-1.5 text-xs"
                onClick={() => setViewMode("editor")}
              >
                <BookOpenTextIcon className="size-3.5" />
                Editor
              </Button>
              <Button
                size="sm"
                variant={viewMode === "collage" ? "default" : "ghost"}
                className="h-7 gap-1.5 text-xs"
                onClick={() => setViewMode("collage")}
              >
                <LayoutPanelTopIcon className="size-3.5" />
                Collage
              </Button>
            </div>
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
          {data && viewMode === "editor" ? <BlockEditorShell document={data} /> : null}
          {data && viewMode === "collage" ? (
            <CollageWorkspace document={data} onSwitchToEditor={() => setViewMode("editor")} />
          ) : null}
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
