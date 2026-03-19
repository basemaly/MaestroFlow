"use client";

import { ArrowRightIcon, BotIcon, PlusIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useAgents } from "@/core/agents";
import type { Agent } from "@/core/agents/types";
import { useI18n } from "@/core/i18n/hooks";

import { AgentCard } from "./agent-card";

export function AgentGallery({ initialAgents }: { initialAgents?: Agent[] }) {
  const { t } = useI18n();
  const { agents, isLoading } = useAgents(initialAgents);
  const router = useRouter();

  const handleNewAgent = () => {
    router.push("/workspace/agents/new");
  };

  return (
    <div className="flex size-full flex-col">
      {/* Page header */}
      <div className="flex items-center justify-between border-b border-border/70 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.06),transparent_28%)] px-6 py-5">
        <div className="max-w-3xl">
          <div className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">Agent Presets</div>
          <h1 className="mt-2 text-xl font-semibold tracking-tight">{t.agents.title}</h1>
          <p className="text-muted-foreground mt-0.5 text-sm">
            {t.agents.description}
          </p>
          <p className="text-muted-foreground mt-1 text-xs">
            Use these as reusable presets across chats, Composer, Executive, and lab workflows.
          </p>
        </div>
        <Button onClick={handleNewAgent}>
          <PlusIcon className="mr-1.5 h-4 w-4" />
          {t.agents.newAgent}
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <div
                key={`agent-skeleton-${index}`}
                className="rounded-2xl border border-border/60 bg-card/60 p-5"
              >
                <div className="mb-4 flex items-center gap-3">
                  <div className="h-10 w-10 animate-pulse rounded-xl bg-muted/60" />
                  <div className="space-y-2">
                    <div className="h-4 w-28 animate-pulse rounded bg-muted/60" />
                    <div className="h-3 w-20 animate-pulse rounded bg-muted/45" />
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="h-3 w-full animate-pulse rounded bg-muted/45" />
                  <div className="h-3 w-[88%] animate-pulse rounded bg-muted/45" />
                  <div className="h-3 w-[72%] animate-pulse rounded bg-muted/45" />
                </div>
              </div>
            ))}
          </div>
        ) : agents.length === 0 ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-border/80 bg-background/70 text-center">
            <div className="bg-muted flex h-14 w-14 items-center justify-center rounded-full">
              <BotIcon className="text-muted-foreground h-7 w-7" />
            </div>
            <div>
              <p className="font-medium">{t.agents.emptyTitle}</p>
              <p className="text-muted-foreground mt-1 text-sm">
                {t.agents.emptyDescription}
              </p>
            </div>
            <Button variant="outline" className="mt-2" onClick={handleNewAgent}>
              <PlusIcon className="mr-1.5 h-4 w-4" />
              {t.agents.newAgent}
              <ArrowRightIcon className="ml-1.5 h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {agents.map((agent) => (
              <AgentCard key={agent.name} agent={agent} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
