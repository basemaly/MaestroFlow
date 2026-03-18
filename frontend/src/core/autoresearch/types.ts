export type AutoresearchDomain = "subagent_prompt" | "workflow_route" | "ui_design";
export type AutoresearchStatus =
  | "draft"
  | "running"
  | "evaluated"
  | "awaiting_approval"
  | "promoted"
  | "rejected"
  | "rolled_back"
  | "stopped";
export type PromotionStatus = "none" | "awaiting_approval" | "approved" | "rejected" | "rolled_back";

export interface ChampionVersion {
  role: string;
  prompt_text: string;
  version: number;
  source_candidate_id?: string | null;
  updated_at: string;
  promoted_by: string;
}

export interface WorkflowTemplateSummary {
  template_id: string;
  title: string;
  description: string;
  objective: string;
  required_outputs: string[];
  node_count: number;
  champion_version: number;
  has_promoted_variant: boolean;
}

export interface ExperimentSummary {
  experiment_id: string;
  domain: AutoresearchDomain;
  role: string;
  title: string;
  status: AutoresearchStatus;
  promotion_status: PromotionStatus;
  champion_version: number;
  candidate_count: number;
  top_score?: number | null;
  updated_at: string;
}

export interface BenchmarkCase {
  case_id: string;
  role: string;
  title: string;
  prompt: string;
  expected_focus: string[];
  validation_hint: string;
}

export interface CandidateScore {
  correctness: number;
  efficiency: number;
  speed: number;
  composite: number;
  notes?: string | null;
}

export interface BenchmarkRunResult {
  case_id: string;
  correctness: number;
  efficiency: number;
  speed: number;
  composite: number;
  elapsed_seconds: number;
  estimated_tokens: number;
  notes?: string | null;
}

export interface CandidateRecord {
  candidate_id: string;
  experiment_id: string;
  role: string;
  prompt_text: string;
  source: "champion" | "mutation" | "manual";
  score?: CandidateScore | null;
  benchmark_case_ids: string[];
  metadata?: Record<string, unknown>;
  created_at: string;
  promoted_at?: string | null;
}

export interface ExperimentRecord {
  experiment_id: string;
  domain: AutoresearchDomain;
  role: string;
  title: string;
  status: AutoresearchStatus;
  champion_version: number;
  champion_prompt: string;
  candidate_ids: string[];
  benchmark_case_ids: string[];
  promotion_status: PromotionStatus;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
  last_error?: string | null;
  notes?: string | null;
}

export interface AutoresearchRegistryPayload {
  manual_start_required?: boolean;
  approval_required?: boolean;
  scheduler_enabled?: boolean;
  domains_enabled?: AutoresearchDomain[];
  roles: string[];
  champions: ChampionVersion[];
  workflow_templates?: WorkflowTemplateSummary[];
}

export interface AutoresearchExperimentDetail {
  experiment: ExperimentRecord;
  benchmarks: BenchmarkCase[];
  candidates: CandidateRecord[];
}
