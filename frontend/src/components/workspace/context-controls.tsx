"use client";

import { BotIcon, CheckIcon, LibraryIcon } from "lucide-react";

import { useAgents } from "@/core/agents";

import {
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuItem,
  PromptInputActionMenuTrigger,
} from "../ai-elements/prompt-input";

import { Tooltip } from "./tooltip";

export type KnowledgeSourceValue = "auto" | "calibre-library";

export function KnowledgeSourceMenu({
  value,
  onChange,
  compact = false,
}: {
  value: KnowledgeSourceValue;
  onChange: (value: KnowledgeSourceValue) => void;
  compact?: boolean;
}) {
  return (
    <PromptInputActionMenu>
      <Tooltip
        content={
          value === "calibre-library"
            ? "Scoped to Calibre Library"
            : "Choose a knowledge source"
        }
      >
        <PromptInputActionMenuTrigger className="gap-1! px-2!">
          <LibraryIcon className="size-3 text-muted-foreground/70" />
          <span className="text-xs">
            {value === "calibre-library"
              ? compact
                ? "Calibre"
                : "Calibre Library"
              : "Auto"}
          </span>
        </PromptInputActionMenuTrigger>
      </Tooltip>
      <PromptInputActionMenuContent className="w-56">
        <PromptInputActionMenuItem onSelect={() => onChange("auto")}>
          Auto knowledge source
        </PromptInputActionMenuItem>
        <PromptInputActionMenuItem onSelect={() => onChange("calibre-library")}>
          Calibre Library
        </PromptInputActionMenuItem>
      </PromptInputActionMenuContent>
    </PromptInputActionMenu>
  );
}

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

  return (
    <PromptInputActionMenu>
      <Tooltip
        content={
          activeAgent
            ? `Preset: ${activeAgent.name}`
            : "Use a custom agent preset"
        }
      >
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
              No specialist preset. Use the standard thread persona.
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
