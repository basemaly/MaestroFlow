"use client";

import { BookCopyIcon, CompassIcon, Layers3Icon } from "lucide-react";

import { Badge } from "@/components/ui/badge";

import { ArtifactTrigger } from "./artifacts";
import { CalibreStatus } from "./calibre-status";
import { AgentPresetMenu, KnowledgeSourceMenu, type KnowledgeSourceValue } from "./context-controls";
import { DocEditDialog } from "./doc-edit-dialog";
import { SnippetShelf } from "./snippet-shelf";
import { SurfSenseActions } from "./surfsense-actions";

export function ContextDock({
  knowledgeSource,
  onKnowledgeSourceChange,
  agentPreset,
  onAgentPresetChange,
  mode,
  disabled,
  includeArtifacts = false,
  includeRevisionLab = false,
}: {
  knowledgeSource: KnowledgeSourceValue;
  onKnowledgeSourceChange: (value: KnowledgeSourceValue) => void;
  agentPreset?: string;
  onAgentPresetChange: (value?: string) => void;
  mode?: "flash" | "thinking" | "pro" | "ultra";
  disabled?: boolean;
  includeArtifacts?: boolean;
  includeRevisionLab?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/70 px-3 py-2 shadow-sm backdrop-blur-sm">
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-muted-foreground flex items-center gap-2 pr-1 text-[11px] font-medium uppercase tracking-[0.16em]">
          <Layers3Icon className="size-3.5" />
          Context Dock
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <KnowledgeSourceMenu
            value={knowledgeSource}
            onChange={onKnowledgeSourceChange}
            compact
          />
          <AgentPresetMenu
            value={agentPreset}
            onChange={onAgentPresetChange}
            compact
          />
          <SurfSenseActions />
          <CalibreStatus />
          {includeRevisionLab ? (
            <DocEditDialog disabled={disabled} mode={mode} />
          ) : null}
          {includeArtifacts ? <ArtifactTrigger /> : null}
          <SnippetShelf />
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className="gap-1 text-[10px]">
            <CompassIcon className="size-3" />
            {knowledgeSource === "calibre-library" ? "Calibre-scoped" : "Auto-scoped"}
          </Badge>
          <Badge variant="outline" className="gap-1 text-[10px]">
            <BookCopyIcon className="size-3" />
            {agentPreset ? `Preset ${agentPreset}` : "Default agent"}
          </Badge>
        </div>
      </div>
    </div>
  );
}
