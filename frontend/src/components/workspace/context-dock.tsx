"use client";

import { BotIcon, DatabaseIcon, WrenchIcon } from "lucide-react";
import { useState } from "react";

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

type DockTab = "source" | "agent" | "tools";

const TAB_META: { id: DockTab; label: string; icon: React.ElementType; tooltip: string }[] = [
  {
    id: "source",
    label: "Source",
    icon: DatabaseIcon,
    tooltip: "Choose a knowledge source — Auto (MaestroFlow), a specific SurfSense search space, or Calibre Library.",
  },
  {
    id: "agent",
    label: "Agent",
    icon: BotIcon,
    tooltip: "Load a specialist agent preset or stay on the default MaestroFlow persona.",
  },
  {
    id: "tools",
    label: "Tools",
    icon: WrenchIcon,
    tooltip: "Context tools: search SurfSense, sync Calibre, manage Pinboard bookmarks, and more.",
  },
];

export function ContextDock({
  knowledgeSource,
  surfsenseSpaceId,
  onKnowledgeSourceChange,
  agentPreset,
  onAgentPresetChange,
  mode,
  disabled,
  includeArtifacts = false,
  includeRevisionLab = false,
}: {
  knowledgeSource: KnowledgeSourceValue;
  surfsenseSpaceId?: number | null;
  onKnowledgeSourceChange: (value: KnowledgeSourceValue, spaceId?: number | null) => void;
  agentPreset?: string;
  onAgentPresetChange: (value?: string) => void;
  mode?: "flash" | "thinking" | "pro" | "ultra";
  disabled?: boolean;
  includeArtifacts?: boolean;
  includeRevisionLab?: boolean;
}) {
  const [activeTab, setActiveTab] = useState<DockTab>("source");

  return (
    <div className="rounded-2xl border border-border/60 bg-background/75 shadow-sm backdrop-blur-sm">
      {/* Tab strip */}
      <div className="flex items-center gap-0 border-b border-border/50 px-2 pt-1.5">
        {TAB_META.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              title={tab.tooltip}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex items-center gap-1.5 border-b-2 px-3 pb-1.5 text-xs font-medium transition-colors",
                isActive
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-3" />
              {tab.label}
            </button>
          );
        })}
        {/* Global actions always visible */}
        <div className="ml-auto flex items-center gap-1 pb-1.5">
          <CalibreStatus />
          {includeRevisionLab ? <DocEditDialog disabled={disabled} mode={mode} /> : null}
          {includeArtifacts ? <ArtifactTrigger /> : null}
          <SnippetShelf />
        </div>
      </div>

      {/* Tab panels */}
      <div className="px-3 py-2">
        {activeTab === "source" && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Knowledge
            </span>
            <KnowledgeSourceMenu
              value={knowledgeSource}
              surfsenseSpaceId={surfsenseSpaceId}
              onChange={onKnowledgeSourceChange}
              compact
            />
            <WorkspaceContextPackChips />
          </div>
        )}

        {activeTab === "agent" && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Agent
            </span>
            <AgentPresetMenu
              value={agentPreset}
              onChange={onAgentPresetChange}
              compact
            />
          </div>
        )}

        {activeTab === "tools" && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Tools
            </span>
            <OpenVikingActions />
            <PinboardActions />
            <CalibreActions />
            <SurfSenseActions />
          </div>
        )}
      </div>
    </div>
  );
}
