"use client";

import { BookCopyIcon, CompassIcon, Layers3Icon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { ArtifactTrigger } from "./artifacts";
import { CalibreActions } from "./calibre-actions";
import { CalibreStatus } from "./calibre-status";
import { AgentPresetMenu, KnowledgeSourceMenu, type KnowledgeSourceValue } from "./context-controls";
import { WorkspaceContextPackChips } from "./context-packs-context";
import { DocEditDialog } from "./doc-edit-dialog";
import { OpenVikingActions } from "./openviking-actions";
import { PinboardActions } from "./pinboard-actions";
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
  const sourceSummary =
    knowledgeSource === "calibre-library" ? "Calibre scoped" : "Auto source";
  const presetSummary = agentPreset ?? "Default preset";

  return (
    <div className="rounded-2xl border border-border/60 bg-background/75 px-3 py-2 shadow-sm backdrop-blur-sm">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="text-muted-foreground flex items-center gap-1.5 pr-1 text-[10px] font-medium uppercase tracking-[0.14em]">
          <Layers3Icon className="size-3.5" />
          Context
        </div>
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
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
          <OpenVikingActions />
          <PinboardActions />
          <CalibreActions />
          <SurfSenseActions />
          <CalibreStatus />
          {includeRevisionLab ? (
            <DocEditDialog disabled={disabled} mode={mode} />
          ) : null}
          {includeArtifacts ? <ArtifactTrigger /> : null}
          <SnippetShelf />
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <Badge
            variant="outline"
            className={cn(
              "gap-1 text-[10px]",
              knowledgeSource === "calibre-library" && "border-sky-500/30 bg-sky-500/5 text-sky-700 dark:text-sky-200",
            )}
          >
            <CompassIcon className="size-3" />
            {sourceSummary}
          </Badge>
          <Badge variant="outline" className="gap-1 text-[10px]">
            <BookCopyIcon className="size-3" />
            {presetSummary}
          </Badge>
        </div>
      </div>
      <div className="mt-2">
        <WorkspaceContextPackChips />
      </div>
    </div>
  );
}
