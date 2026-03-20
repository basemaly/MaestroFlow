"use client";

import {
  BookOpenTextIcon,
  Loader2Icon,
  LayoutPanelTopIcon,
  PanelRightIcon,
  Settings2Icon,
} from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { BreadcrumbItem, BreadcrumbPage } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import type { BlockEditorHandle } from "@/components/workspace/block-editor/block-editor";
import { BlockEditorShell } from "@/components/workspace/block-editor/block-editor-shell";
import { CollageWorkspace } from "@/components/workspace/collage/collage-workspace";
import { BlocksSidebar } from "@/components/workspace/composer/blocks-sidebar";
import { ContextDock } from "@/components/workspace/context-dock";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { loadBlocks } from "@/core/documents/collage-blocks";
import { useDocument } from "@/core/documents/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { useLocalSettings } from "@/core/settings";
import { cn } from "@/lib/utils";

export default function ComposerDocumentPage() {
  const { doc_id } = useParams<{ doc_id: string }>();
  const { data, isLoading, isError } = useDocument(doc_id);
  const { t } = useI18n();
  const [settings, setSettings] = useLocalSettings();
  const [viewMode, setViewMode] = useState<"editor" | "collage">("editor");
  const [contextOpen, setContextOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const editorHandleRef = useRef<BlockEditorHandle | null>(null);

  // Block count badge — reads from localStorage with reduced poll frequency
  const [blockCount, setBlockCount] = useState(0);
  useEffect(() => {
    if (!doc_id) return;
    const refresh = () => setBlockCount(loadBlocks(doc_id).length);
    refresh();
    // Poll every 5 seconds instead of 3 to reduce overhead
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [doc_id]);

  useEffect(() => {
    document.title = `${data?.title ?? t.pages.untitled} - ${t.pages.appName}`;
  }, [data?.title, t.pages.appName, t.pages.untitled]);

  const headerRight = (
    <div className="flex items-center gap-1.5">
      {/* Document title */}
      {data?.title && (
        <span className="hidden max-w-[160px] truncate text-xs font-medium text-foreground/70 lg:block">
          {data.title}
        </span>
      )}
      {/* View mode toggle */}
      <div className="flex items-center gap-0.5 rounded-xl border border-border/70 bg-muted/30 p-0.5">
        <Button
          size="sm"
          variant={viewMode === "editor" ? "default" : "ghost"}
          className="h-7 gap-1 rounded-lg px-2.5 text-xs"
          onClick={() => setViewMode("editor")}
        >
          <BookOpenTextIcon className="size-3" />
          <span className="hidden sm:inline">Composer</span>
        </Button>
        <Button
          size="sm"
          variant={viewMode === "collage" ? "default" : "ghost"}
          className="h-7 gap-1 rounded-lg px-2.5 text-xs"
          onClick={() => setViewMode("collage")}
        >
          <LayoutPanelTopIcon className="size-3" />
          <span className="hidden sm:inline">Collage</span>
        </Button>
      </div>
      {/* Blocks sidebar toggle (only in editor mode) */}
      {viewMode === "editor" && (
        <Button
          size="sm"
          variant={sidebarOpen ? "secondary" : "ghost"}
          className="relative h-7 gap-1 rounded-xl px-2.5 text-xs"
          onClick={() => setSidebarOpen((v) => !v)}
          title="Toggle blocks panel"
        >
          <PanelRightIcon className="size-3" />
          <span className="hidden sm:inline">Blocks</span>
          {blockCount > 0 && (
            <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-primary text-[9px] text-primary-foreground">
              {blockCount}
            </span>
          )}
        </Button>
      )}
      {/* Context toggle */}
      <Button
        size="sm"
        variant={contextOpen ? "secondary" : "ghost"}
        className="h-7 gap-1 rounded-xl px-2.5 text-xs"
        onClick={() => setContextOpen((v) => !v)}
        title="Toggle context settings"
      >
        <Settings2Icon className="size-3" />
        <span className="hidden sm:inline">Context</span>
      </Button>
    </div>
  );

  return (
    <WorkspaceContainer>
      <WorkspaceHeader rightSlot={headerRight}>
        <BreadcrumbItem>
          <BreadcrumbPage className="max-w-[120px] truncate text-xs">
            {data?.title ?? (isLoading ? "Loading…" : "Untitled")}
          </BreadcrumbPage>
        </BreadcrumbItem>
      </WorkspaceHeader>
      <WorkspaceBody>
        <div className="flex size-full min-h-0 flex-col bg-[radial-gradient(circle_at_top_left,rgba(217,119,6,0.08),transparent_28%),radial-gradient(circle_at_top_right,rgba(20,83,45,0.08),transparent_24%)]">
          {/* Collapsible context dock strip */}
          {contextOpen && (
            <div className="shrink-0 border-b border-border/70 bg-background/85 px-4 py-2 backdrop-blur-sm">
              <ContextDock
                knowledgeSource={
                  (settings.context.knowledge_source as "auto" | "calibre-library" | "surfsense" | undefined) ??
                  "auto"
                }
                surfsenseSpaceId={
                  typeof settings.context.surfsense_search_space_id === "number"
                    ? settings.context.surfsense_search_space_id
                    : null
                }
                onKnowledgeSourceChange={(knowledge_source, spaceId) =>
                  setSettings("context", { knowledge_source, surfsense_search_space_id: spaceId ?? undefined })
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
          )}
          {/* Main content area */}
          <div className={cn("flex min-h-0 flex-1 gap-4", viewMode === "collage" ? "p-4" : "p-6")}>
            {/* Editor or Collage */}
            <div className="min-w-0 flex-1">
              {isLoading && !data ? (
                <div className="flex h-full items-center justify-center">
                  <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border/60 bg-background/40 px-8 py-12 backdrop-blur-xs">
                    <Loader2Icon className="size-5 animate-spin text-primary" />
                    <div className="text-sm font-medium text-muted-foreground">Loading composer draft…</div>
                  </div>
                </div>
              ) : null}
              {!isLoading && isError ? (
                <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
                  Could not load composer draft.
                </div>
              ) : null}
              {data && viewMode === "editor" ? (
                <BlockEditorShell document={data} editorHandleRef={editorHandleRef} />
              ) : null}
              {data && viewMode === "collage" ? (
                <CollageWorkspace document={data} onSwitchToEditor={() => setViewMode("editor")} />
              ) : null}
            </div>
            {/* Blocks sidebar — only shown in editor mode when open */}
            {viewMode === "editor" && sidebarOpen && doc_id ? (
              <BlocksSidebar
                docId={doc_id}
                editorHandleRef={editorHandleRef}
                onSwitchToCollage={() => {
                  setSidebarOpen(false);
                  setViewMode("collage");
                }}
              />
            ) : null}
          </div>
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
