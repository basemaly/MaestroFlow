export type PlanningComplexity =
  | "simple"
  | "complex"
  | "high_ambiguity"
  | "high_cost";

export type PlanningReviewStatus =
  | "drafting_plan"
  | "plan_review"
  | "awaiting_clarification"
  | "executing_approved_plan"
  | "executing_unreviewed_plan"
  | "completed";

export type PromptAudit = {
  issues: string[];
  optimized_prompt: string;
  rationale: string;
};

export type PlanRecommendations = {
  model_name?: string | null;
  mode?: string | null;
  thinking_enabled: boolean;
  reasoning_effort?: string | null;
  tools: string[];
  subagent_count: number;
  rationale: string;
};

export type PlanStep = {
  step_id: string;
  title: string;
  status: "pending" | "in_progress" | "completed";
  enabled: boolean;
  kind: string;
  notes?: string | null;
  details?: string | null;
  sources: string[];
  expected_output?: string | null;
  estimated_cost: "low" | "medium" | "high";
  estimated_latency: "fast" | "moderate" | "slow";
};

export type PlanDraft = {
  summary: string;
  rationale: string;
  steps: PlanStep[];
  estimated_cost: "low" | "medium" | "high";
  estimated_latency: "fast" | "moderate" | "slow";
  review_required: boolean;
  prompt_audit?: PromptAudit | null;
  recommendations?: PlanRecommendations | null;
};

export type ClarificationQuestion = {
  question_id: string;
  question: string;
  rationale: string;
  kind: "scope" | "audience" | "constraints" | "format" | "priority";
  options: string[];
};

export type ExecutiveSuggestion = {
  suggestion_id: string;
  kind:
    | "ask_clarification"
    | "reframe_prompt"
    | "switch_workflow"
    | "toggle_tool"
    | "adjust_depth"
    | "adjust_output_format"
    | "warn_degraded_service";
  severity: "low" | "medium" | "high";
  title: string;
  summary: string;
  rationale: string;
  prompt_patch?: string | null;
  context_patch: Record<string, unknown>;
  requires_confirmation: boolean;
};

export type FirstTurnReviewResponse = {
  thread_id: string;
  status: PlanningReviewStatus;
  complexity: PlanningComplexity;
  review_required: boolean;
  plan: PlanDraft;
  suggestions: ExecutiveSuggestion[];
  questions: ClarificationQuestion[];
  trace_id?: string | null;
};

export type PlanApprovalResult = {
  thread_id: string;
  status: PlanningReviewStatus;
  prompt: string;
  context_patch: Record<string, unknown>;
  applied_suggestion_ids: string[];
  review_required: boolean;
};
