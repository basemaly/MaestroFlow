import type { TaskArtifact, TaskQuality } from "./types";

export interface ParsedTaskResult {
  status: "completed" | "failed" | "timed_out";
  subagent_type: string;
  result?: string;
  error?: string;
  artifact?: TaskArtifact;
  quality?: TaskQuality;
  visibleText: string;
}

const METADATA_RE = /<task-metadata>([\s\S]*?)<\/task-metadata>/;

export function parseTaskToolResult(rawText: string): ParsedTaskResult | null {
  const match = METADATA_RE.exec(rawText);
  if (!match) {
    return null;
  }

  try {
    const payload = JSON.parse(match[1] ?? "{}") as Omit<ParsedTaskResult, "visibleText">;
    if (!payload?.status || !payload?.subagent_type) {
      return null;
    }
    return {
      ...payload,
      visibleText: rawText.replace(METADATA_RE, "").trim(),
    };
  } catch {
    return null;
  }
}
