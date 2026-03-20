"use client";

import { BotIcon, CheckIcon, DatabaseIcon, LibraryIcon, Loader2Icon, WavesIcon } from "lucide-react";

import { useAgents } from "@/core/agents";
import { useSurfSenseSearchSpaces } from "@/core/surfsense/hooks";

import {
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuItem,
  PromptInputActionMenuTrigger,
} from "../ai-elements/prompt-input";

import { Tooltip } from "./tooltip";

export type KnowledgeSourceValue = "auto" | "calibre-library" | "surfsense";

// ─── Knowledge source menu ────────────────────────────────────────────────────

const SOURCE_LABELS: Record<KnowledgeSourceValue, string> = {
  auto: "Auto",
  "calibre-library": "Calibre",
  surfsense: "SurfSense",
};

const SOURCE_ICON: Record<KnowledgeSourceValue, React.ElementType> = {
  auto: DatabaseIcon,
  "calibre-library": LibraryIcon,
  surfsense: WavesIcon,
};

function knowledgeTooltip(
  value: KnowledgeSourceValue,
  spaceName: string | null,
): string {
  if (value === "calibre-library") {
    return "Calibre Library mode — the agent prioritises your local Calibre ebook collection for book, author, and passage questions, and can ingest books into SurfSense on request.";
  }
  if (value === "surfsense") {
    return spaceName
      ? `SurfSense space "${spaceName}" — every knowledge query goes directly to this search space.`
      : "SurfSense mode — every knowledge query is routed to the selected SurfSense search space.";
  }
  return "Auto mode — routes to the MaestroFlow SurfSense search space by default. Automatically uses your Calibre library when a question calls for book-level evidence.";
}

export function KnowledgeSourceMenu({
  value,
  surfsenseSpaceId,
  onChange,
  compact = false,
}: {
  value: KnowledgeSourceValue;
  surfsenseSpaceId?: number | null;
  onChange: (value: KnowledgeSourceValue, spaceId?: number | null) => void;
  compact?: boolean;
}) {
  const { spaces, loading } = useSurfSenseSearchSpaces();
  const activeSpace = spaces.find((s) => s.id === surfsenseSpaceId) ?? null;

  const label = (() => {
    if (value === "surfsense" && activeSpace) return compact ? activeSpace.name : `SS: ${activeSpace.name}`;
    if (value === "surfsense") return compact ? "SurfSense" : "SurfSense";
    return compact ? SOURCE_LABELS[value] : SOURCE_LABELS[value];
  })();

  const Icon = SOURCE_ICON[value];

  return (
    <PromptInputActionMenu>
      <Tooltip content={knowledgeTooltip(value, activeSpace?.name ?? null)}>
        <PromptInputActionMenuTrigger className="gap-1! px-2!">
          <Icon className="size-3 text-muted-foreground/70" />
          <span className="max-w-[8rem] truncate text-xs">{label}</span>
        </PromptInputActionMenuTrigger>
      </Tooltip>
      <PromptInputActionMenuContent className="w-72">
        {/* Auto */}
        <PromptInputActionMenuItem onSelect={() => onChange("auto", null)}>
          <div className="flex min-w-0 flex-col gap-0.5">
            <div className="font-medium">Auto (MaestroFlow)</div>
            <div className="text-muted-foreground text-xs">
              Routes to the MaestroFlow SurfSense space. Falls back to Calibre for book-level questions.
            </div>
          </div>
          {value === "auto" && <CheckIcon className="ml-auto size-4 shrink-0" />}
        </PromptInputActionMenuItem>

        {/* Calibre Library */}
        <PromptInputActionMenuItem onSelect={() => onChange("calibre-library", null)}>
          <div className="flex min-w-0 flex-col gap-0.5">
            <div className="flex items-center gap-1.5 font-medium">
              <LibraryIcon className="size-3" />
              Calibre Library
            </div>
            <div className="text-muted-foreground text-xs">
              All book, author, and passage queries go to your local Calibre collection first. The agent can also ingest books into a SurfSense search space on request.
            </div>
          </div>
          {value === "calibre-library" && <CheckIcon className="ml-auto size-4 shrink-0" />}
        </PromptInputActionMenuItem>

        {/* SurfSense spaces */}
        {loading && (
          <PromptInputActionMenuItem onSelect={() => undefined} disabled>
            <Loader2Icon className="size-3 animate-spin text-muted-foreground" />
            <span className="text-muted-foreground text-xs">Loading search spaces…</span>
          </PromptInputActionMenuItem>
        )}
        {!loading && spaces.length > 0 && (
          <>
            <div className="px-2 py-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              SurfSense Spaces
            </div>
            {spaces.map((space) => (
              <PromptInputActionMenuItem
                key={space.id}
                onSelect={() => onChange("surfsense", space.id)}
              >
                <div className="flex min-w-0 flex-col gap-0.5">
                  <div className="flex items-center gap-1.5 font-medium">
                    <WavesIcon className="size-3" />
                    {space.name}
                  </div>
                  <div className="text-muted-foreground text-xs">
                    All knowledge queries go directly to this SurfSense search space.
                  </div>
                </div>
                {value === "surfsense" && surfsenseSpaceId === space.id && (
                  <CheckIcon className="ml-auto size-4 shrink-0" />
                )}
              </PromptInputActionMenuItem>
            ))}
          </>
        )}
        {!loading && spaces.length === 0 && (
          <PromptInputActionMenuItem onSelect={() => undefined} disabled>
            <div className="text-muted-foreground text-xs">
              No SurfSense search spaces found. Check your SurfSense configuration.
            </div>
          </PromptInputActionMenuItem>
        )}
      </PromptInputActionMenuContent>
    </PromptInputActionMenu>
  );
}

// ─── Agent preset menu ────────────────────────────────────────────────────────

function compactAgentDescription(agent: {
  description: string;
  model: string | null;
}): string {
  if (agent.description?.trim()) {
    return agent.description.trim();
  }
  if (agent.model?.trim()) {
    return `Uses ${agent.model}`;
  }
  return "Reusable specialist preset";
}

export function AgentPresetMenu({
  value,
  onChange,
  compact = false,
}: {
  value?: string;
  onChange: (value?: string) => void;
  compact?: boolean;
}) {
  const { agents } = useAgents();
  const activeAgent = agents.find((agent) => agent.name === value);

  const tooltipText = activeAgent
    ? `Agent preset "${activeAgent.name}" is active — ${compactAgentDescription(activeAgent)}. Click to switch presets or revert to the default MaestroFlow persona.`
    : "No specialist preset selected. The default MaestroFlow agent handles all requests. Select a preset to load a custom role, model, or instruction set.";

  return (
    <PromptInputActionMenu>
      <Tooltip content={tooltipText}>
        <PromptInputActionMenuTrigger className="gap-1! px-2!">
          <BotIcon className="size-3 text-muted-foreground/70" />
          <span className="max-w-[9rem] truncate text-xs">
            {activeAgent
              ? compact
                ? activeAgent.name
                : `Preset: ${activeAgent.name}`
              : compact
                ? "Preset"
                : "Agent Preset"}
          </span>
        </PromptInputActionMenuTrigger>
      </Tooltip>
      <PromptInputActionMenuContent className="w-72">
        <PromptInputActionMenuItem onSelect={() => onChange(undefined)}>
          <div className="flex min-w-0 flex-col gap-1">
            <div className="font-medium">Default MaestroFlow</div>
            <div className="text-muted-foreground text-xs">
              Standard MaestroFlow persona with full tool access. No specialist customisation.
            </div>
          </div>
          {!value ? (
            <CheckIcon className="ml-auto size-4 shrink-0" />
          ) : (
            <div className="ml-auto size-4 shrink-0" />
          )}
        </PromptInputActionMenuItem>
        {agents.map((agent) => (
          <PromptInputActionMenuItem
            key={agent.name}
            onSelect={() => onChange(agent.name)}
          >
            <div className="flex min-w-0 flex-col gap-1">
              <div className="truncate font-medium">{agent.name}</div>
              <div className="text-muted-foreground line-clamp-2 text-xs">
                {compactAgentDescription(agent)}
              </div>
            </div>
            {value === agent.name ? (
              <CheckIcon className="ml-auto size-4 shrink-0" />
            ) : (
              <div className="ml-auto size-4 shrink-0" />
            )}
          </PromptInputActionMenuItem>
        ))}
      </PromptInputActionMenuContent>
    </PromptInputActionMenu>
  );
}
