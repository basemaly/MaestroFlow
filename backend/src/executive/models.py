from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ExecutiveState = Literal["healthy", "degraded", "unavailable", "misconfigured", "disabled", "unknown"]
ExecutiveRiskLevel = Literal["low", "medium", "high", "critical"]
ExecutiveActionStatus = Literal["preview", "pending_approval", "approved", "rejected", "succeeded", "failed"]


class ExecutiveDependency(BaseModel):
    component_id: str
    label: str
    state: ExecutiveState = "unknown"


class ExecutiveRecommendation(BaseModel):
    title: str
    summary: str
    action_id: str | None = None
    component_id: str | None = None
    priority: int = Field(default=2, ge=0, le=3)


class ExecutiveActionDefinition(BaseModel):
    action_id: str
    label: str
    description: str
    component_scope: list[str] = Field(default_factory=list)
    risk_level: ExecutiveRiskLevel = "low"
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ExecutiveComponent(BaseModel):
    component_id: str
    label: str
    kind: str
    owner: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    status_adapter: str
    actions: list[str] = Field(default_factory=list)
    best_practices: list[str] = Field(default_factory=list)
    risk_level: ExecutiveRiskLevel = "low"
    managed_scope: Literal["observe_only", "configurable", "host_managed"] = "observe_only"
    requires_confirmation_for: list[str] = Field(default_factory=list)


class ExecutiveStatusSnapshot(BaseModel):
    component_id: str
    label: str
    state: ExecutiveState = "unknown"
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[ExecutiveDependency] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutiveActionRequest(BaseModel):
    action_id: str
    component_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = "user"


class ExecutiveActionPreview(BaseModel):
    action_id: str
    component_id: str
    risk_level: ExecutiveRiskLevel
    requires_confirmation: bool
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutiveExecutionResult(BaseModel):
    action_id: str
    component_id: str
    status: ExecutiveActionStatus
    risk_level: ExecutiveRiskLevel
    requires_confirmation: bool
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = None


class ExecutiveApprovalRequest(BaseModel):
    approval_id: str
    created_at: datetime
    requested_by: str
    component_id: str
    action_id: str
    preview: ExecutiveActionPreview
    input: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    expires_at: datetime | None = None


class ExecutiveAuditEntry(BaseModel):
    audit_id: str
    timestamp: datetime
    actor_type: str
    actor_id: str
    component_id: str
    action_id: str
    input_summary: str
    risk_level: ExecutiveRiskLevel
    required_confirmation: bool
    status: ExecutiveActionStatus
    result_summary: str
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutiveAdvisoryRule(BaseModel):
    rule_id: str
    title: str
    summary: str
    severity: ExecutiveRiskLevel = "low"
    component_id: str | None = None
    recommendation: ExecutiveRecommendation | None = None


class ExecutiveSystemStatus(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: dict[str, int] = Field(default_factory=dict)
    components: list[ExecutiveStatusSnapshot] = Field(default_factory=list)


class ExecutiveChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ExecutiveChatResponse(BaseModel):
    answer: str
    recommendations: list[ExecutiveRecommendation] = Field(default_factory=list)
    action_preview: ExecutiveActionPreview | None = None
    component_refs: list[str] = Field(default_factory=list)
    advisory_refs: list[str] = Field(default_factory=list)
