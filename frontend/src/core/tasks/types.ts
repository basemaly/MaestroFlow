import type { AIMessage } from "@langchain/langgraph-sdk";

export interface TaskArtifact {
  schema: string;
  word_count: number;
  has_sources: boolean;
  has_errors: boolean;
  quality_warnings: string[];
  sections_present: string[];
  expected_sections: string[];
  is_valid: boolean;
}

export interface TaskQuality {
  task_id: string;
  thread_id?: string | null;
  subagent_type: string;
  schema: string;
  completeness: number;
  source_quality: number;
  error_rate: number;
  composite: number;
  word_count: number;
  dimensions: Record<string, number>;
  quality_warnings: string[];
  profile: string;
  scored_at?: string;
}

export interface Subtask {
  id: string;
  status: "in_progress" | "completed" | "failed";
  subagent_type: string;
  description: string;
  latestMessage?: AIMessage;
  prompt: string;
  result?: string;
  error?: string;
  artifact?: TaskArtifact;
  quality?: TaskQuality;
}
