import { AgentGallery } from "@/components/workspace/agents/agent-gallery";
import type { Agent } from "@/core/agents/types";
import { getServerAppOrigin } from "@/core/server/app-origin";

async function loadInitialAgents(): Promise<Agent[] | null> {
  try {
    const origin = await getServerAppOrigin();
    const response = await fetch(`${origin}/api/agents`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as { agents?: Agent[] };
    return payload.agents ?? [];
  } catch {
    return null;
  }
}

export default async function AgentsPage() {
  const initialAgents = await loadInitialAgents();
  return <AgentGallery initialAgents={initialAgents ?? undefined} />;
}
