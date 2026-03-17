export type ExecutiveRiskLevel = "low" | "medium" | "high" | "critical";
export type ExecutiveState =
  | "healthy"
  | "degraded"
  | "unavailable"
  | "misconfigured"
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
