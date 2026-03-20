import type { Message, Thread } from "@langchain/langgraph-sdk";

import type { Todo } from "../todos";

export interface AgentThreadState extends Record<string, unknown> {
  title: string;
  messages: Message[];
  artifacts: string[];
  todos?: Todo[];
}

export interface AgentThread extends Thread<AgentThreadState> {}

export interface AgentThreadContext extends Record<string, unknown> {
  thread_id: string;
  model_name: string | undefined;
  thinking_enabled: boolean;
  is_plan_mode: boolean;
  subagent_enabled: boolean;
  reasoning_effort?: "minimal" | "low" | "medium" | "high";
  subagent_model?: string;
  agent_name?: string;
  knowledge_source?: "auto" | "calibre-library" | "surfsense";
  /** When knowledge_source === "surfsense", the explicit search space to route to */
  surfsense_search_space_id?: number | null;
  /** Opt-in research tool group names to enable, e.g. ["opt:exa", "opt:serper"] */
  research_tools?: string[];
}
