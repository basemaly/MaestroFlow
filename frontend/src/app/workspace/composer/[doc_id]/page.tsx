"use client";

import { BookOpenTextIcon, LayoutPanelTopIcon } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { BlockEditorShell } from "@/components/workspace/block-editor/block-editor-shell";
import { CollageWorkspace } from "@/components/workspace/collage/collage-workspace";
import { ContextDock } from "@/components/workspace/context-dock";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useDocument } from "@/core/documents/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { useLocalSettings } from "@/core/settings";

export default function ComposerDocumentPage() {
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
        <div className="size-full min-h-0 bg-[radial-gradient(circle_at_top_left,rgba(217,119,6,0.08),transparent_28%),radial-gradient(circle_at_top_right,rgba(20,83,45,0.08),transparent_24%)] p-6">
          <div className="mb-4 rounded-3xl border border-border/70 bg-background/80 p-4 shadow-sm backdrop-blur">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-3">
                <div className="space-y-1">
                  <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
                    Composer Desk
                  </div>
                  <div className="text-xl font-semibold tracking-tight">
                    {data?.title ?? "Untitled piece"}
                  </div>
                  <div className="max-w-2xl text-sm text-muted-foreground">
                    Draft in Composer, spread fragments into Collage, then route polished sections through Revision Lab when you need alternate takes.
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="rounded-full border border-border/70 bg-muted/40 px-2.5 py-1">
                    {data?.status ?? "loading"}
                  </span>
                  <span className="rounded-full border border-border/70 bg-muted/40 px-2.5 py-1">
                    {viewMode === "editor" ? "Writing view" : "Assembly view"}
                  </span>
                </div>
              </div>
              <div className="flex w-full flex-col gap-3 xl:w-auto xl:min-w-[28rem]">
                <div className="flex items-center gap-1 self-start rounded-2xl border border-border/70 bg-muted/30 p-1">
                  <Button
                    size="sm"
                    variant={viewMode === "editor" ? "default" : "ghost"}
                    className="h-8 gap-1.5 rounded-xl px-3 text-xs"
                    onClick={() => setViewMode("editor")}
                  >
                    <BookOpenTextIcon className="size-3.5" />
                    Composer
                  </Button>
                  <Button
                    size="sm"
                    variant={viewMode === "collage" ? "default" : "ghost"}
                    className="h-8 gap-1.5 rounded-xl px-3 text-xs"
                    onClick={() => setViewMode("collage")}
                  >
                    <LayoutPanelTopIcon className="size-3.5" />
                    Collage
                  </Button>
                </div>
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
            </div>
          </div>
          {isLoading && !data ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Loading composer draft...
            </div>
          ) : null}
          {!isLoading && isError ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              Could not load composer draft.
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
