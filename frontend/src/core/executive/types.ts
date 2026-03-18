export type ExecutiveRiskLevel = "low" | "medium" | "high" | "critical";
export type ExecutiveState =
  | "healthy"
  | "degraded"
  | "unavailable"
  | "misconfigured"
  | "disabled"
  | "unknown";

export type ExecutiveRecommendation = {
  title: string;
  summary: string;
  action_id?: string | null;
  component_id?: string | null;
  priority: number;
};

export type ExecutiveActionDefinition = {
  action_id: string;
  label: string;
  description: string;
  component_scope: string[];
  risk_level: ExecutiveRiskLevel;
  requires_confirmation: boolean;
  input_schema: Record<string, unknown>;
};

export type ExecutiveComponent = {
  component_id: string;
  label: string;
  kind: string;
  owner: string;
  description: string;
  dependencies: string[];
  status_adapter: string;
  actions: string[];
  best_practices: string[];
  risk_level: ExecutiveRiskLevel;
  managed_scope: "observe_only" | "configurable" | "host_managed";
  requires_confirmation_for: string[];
};

export type ExecutiveStatusSnapshot = {
  component_id: string;
  label: string;
  state: ExecutiveState;
  summary: string;
  details: Record<string, unknown>;
  metrics: Record<string, unknown>;
  dependencies: Array<{
    component_id: string;
    label: string;
    state: ExecutiveState;
  }>;
  recommended_actions: string[];
  checked_at: string;
};

export type ExecutiveSystemStatus = {
  generated_at: string;
  summary: Record<string, number>;
  components: ExecutiveStatusSnapshot[];
};

export type ExecutiveActionPreview = {
  action_id: string;
  component_id: string;
  risk_level: ExecutiveRiskLevel;
  requires_confirmation: boolean;
  summary: string;
  details: Record<string, unknown>;
};

export type ExecutiveExecutionResult = {
  action_id: string;
  component_id: string;
  status:
    | "preview"
    | "pending_approval"
    | "approved"
    | "rejected"
    | "succeeded"
    | "failed";
  risk_level: ExecutiveRiskLevel;
  requires_confirmation: boolean;
  summary: string;
  details: Record<string, unknown>;
  approval_id?: string | null;
};

export type ExecutiveApprovalRequest = {
  approval_id: string;
  created_at: string;
  requested_by: string;
  component_id: string;
  action_id: string;
  preview: ExecutiveActionPreview;
  input: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "expired";
  expires_at?: string | null;
};

export type ExecutiveAuditEntry = {
  audit_id: string;
  timestamp: string;
  actor_type: string;
  actor_id: string;
  component_id: string;
  action_id: string;
  input_summary: string;
  risk_level: ExecutiveRiskLevel;
  required_confirmation: boolean;
  status: string;
  result_summary: string;
  error?: string | null;
  details: Record<string, unknown>;
};

export type ExecutiveAdvisoryRule = {
  rule_id: string;
  title: string;
  summary: string;
  severity: ExecutiveRiskLevel;
  component_id?: string | null;
  recommendation?: ExecutiveRecommendation | null;
};

// ---------------------------------------------------------------------------
// Project Orchestration Types
// ---------------------------------------------------------------------------

export type ProjectStatus =
  | "planning"
  | "waiting_approval"
  | "running"
  | "paused"
  | "completed"
  | "cancelled"
  | "failed";

export type StageStatus =
  | "pending"
  | "waiting_approval"
  | "running"
  | "completed"
  | "skipped"
  | "failed";

export type StageKind =
  | "research"
  | "draft"
  | "edit"
  | "fact_check"
  | "critique"
  | "synthesize"
  | "finalize"
  | "custom";

export type CheckpointKind = "pre_stage" | "post_stage" | "iteration" | "goal_check";

export type StageOutputRecord = {
  iteration: number;
  output: string;
  quality_score?: number | null;
  created_at: string;
};

export type StageInfo = {
  stage_id: string;
  title: string;
  kind: StageKind;
  status: StageStatus;
  iteration_count: number;
  max_iterations: number;
  output_preview?: string | null;
  current_output?: string | null;
  outputs?: StageOutputRecord[];
  error?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  agent_id?: string | null;
};

export type CheckpointInfo = {
  checkpoint_id: string;
  stage_id?: string | null;
  title: string;
  description: string;
  kind: CheckpointKind;
  status: "pending" | "approved" | "rejected";
  created_at: string;
};

export type ProjectSummary = {
  project_id: string;
  title: string;
  status: ProjectStatus;
  current_stage?: string | null;
  current_stage_index: number;
  total_stages: number;
  total_iterations: number;
  pending_checkpoint?: string | null;
  created_at: string;
  updated_at: string;
};

export type ExecutiveProject = ProjectSummary & {
  goal: string;
  stages: StageInfo[];
  checkpoints: CheckpointInfo[];
  context: Record<string, unknown>;
  started_at?: string | null;
  completed_at?: string | null;
  deadline?: string | null;
};

export type CreateProjectParams = {
  title: string;
  goal: string;
  stages: Record<string, unknown>[];
  options?: Record<string, unknown>;
};

export type AdvanceProjectResponse = {
  project_id: string;
  status: string;
  stage_id?: string | null;
  stage_title?: string | null;
  iteration?: number | null;
  checkpoint_id?: string | null;
  message: string;
};
