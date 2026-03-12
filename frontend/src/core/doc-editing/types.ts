export interface DocEditVersion {
  skill_name: string;
  subagent_type?: string;
  output?: string;
  score: number;
  quality_dims?: Record<string, number>;
  token_count?: number;
  latency_ms?: number;
  file_path?: string;
  model_name?: string;
}

export interface DocEditReviewPayload {
  run_id?: string;
  status?: string;
  instruction?: string;
  suggested_skill?: string;
  versions_summary?: Array<{
    rank: number;
    skill_name: string;
    score: number;
    file_path?: string;
    preview?: string;
  }>;
}

export interface DocEditRun {
  run_id: string;
  title?: string;
  run_dir: string;
  status: "awaiting_selection" | "completed";
  document?: string;
  final_path: string | null;
  selected_skill: string | null;
  versions: DocEditVersion[];
  token_count: number;
  review_payload?: DocEditReviewPayload | null;
}

export interface DocEditRunsResponse {
  runs: Array<{
    run_id: string;
    title?: string;
    timestamp?: string | null;
    doc_length?: number | null;
    skills_used?: string[];
    selected_skill?: string | null;
    composite_score?: number | null;
    token_count?: number;
    model_used?: string | null;
    final_path?: string | null;
    status: "awaiting_selection" | "completed";
  }>;
}
