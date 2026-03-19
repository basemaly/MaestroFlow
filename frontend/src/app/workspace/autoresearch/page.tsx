import { ArrowRightIcon, BotIcon, FlaskConicalIcon } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { AutoresearchPageClient } from "@/components/workspace/autoresearch/autoresearch-page-client";
import type { AutoresearchRegistryPayload, ExperimentSummary } from "@/core/autoresearch/types";
import { getServerAppOrigin } from "@/core/server/app-origin";

async function loadInitialData(): Promise<{
  registry: AutoresearchRegistryPayload;
  experiments: ExperimentSummary[];
}> {
  try {
    const origin = await getServerAppOrigin();
    const [registryResponse, experimentsResponse] = await Promise.all([
      fetch(`${origin}/api/autoresearch/registry`, { cache: "no-store" }),
      fetch(`${origin}/api/autoresearch/experiments`, { cache: "no-store" }),
    ]);
    const registry = registryResponse.ok
      ? ((await registryResponse.json()) as AutoresearchRegistryPayload)
      : { roles: [], champions: [] };
    const experimentsPayload = experimentsResponse.ok
      ? ((await experimentsResponse.json()) as { experiments?: ExperimentSummary[] })
      : { experiments: [] };
    return {
      registry,
      experiments: experimentsPayload.experiments ?? [],
    };
  } catch {
    return {
      registry: { roles: [], champions: [] },
      experiments: [],
    };
  }
}

export default async function AutoresearchPage() {
  const initialData = await loadInitialData();
  return (
    <div className="flex size-full flex-col bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.08),transparent_22%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.05),transparent_20%)]">
      <div className="border-b border-border/70 px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
              <FlaskConicalIcon className="h-3.5 w-3.5" />
              Manual optimization lab
            </div>
            <h1 className="text-xl font-semibold">Autoresearcher</h1>
            <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
              A dedicated lab for prompt and workflow experiments. It stays separate from Executive and from normal agent
              presets so experiments do not silently mutate live behavior.
            </p>
            <p className="text-muted-foreground mt-2 max-w-2xl text-xs">
              Start one experiment at a time, compare the candidates, and only promote changes that beat the current baseline.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href="/workspace/chats/new">
                Open a fresh chat
                <ArrowRightIcon className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
            <Button asChild>
              <Link href="/workspace/agents">
                View agent presets
                <BotIcon className="ml-1.5 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <AutoresearchPageClient registry={initialData.registry} experiments={initialData.experiments} />
      </div>
    </div>
  );
}
