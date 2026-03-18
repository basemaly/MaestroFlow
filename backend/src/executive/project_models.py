"""Pydantic models for Executive Agent project orchestration."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class StageKind(str, Enum):
    RESEARCH = "research"
    DRAFT = "draft"
    EDIT = "edit"
    FACT_CHECK = "fact_check"
    CRITIQUE = "critique"
    SYNTHESIZE = "synthesize"
    FINALIZE = "finalize"
    CUSTOM = "custom"


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class StageStatus(str, Enum):
    PENDING = "pending"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class IterationPolicy(BaseModel):
    """Controls how many times and under what conditions a stage can repeat."""

    max_iterations: int = Field(default=3, ge=1, le=20)
    goal_check_prompt: str | None = Field(
        default=None,
        description="LLM prompt to evaluate whether iteration goal has been met. "
        "If provided, the LLM is asked after each iteration. "
        "Example: 'Is this draft publication-ready? Answer yes or no with brief rationale.'",
    )
    quality_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum quality score (0–1) assessed by LLM. Stage retries until met.",
    )
    require_approval_each: bool = Field(
        default=False,
        description="Pause and ask user for approval after every iteration.",
    )


class StageOutput(BaseModel):
    """A single iteration's output from a workflow stage."""

    iteration: int
    output: str
    thread_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="LLM-assessed quality score for this output.",
    )


class WorkflowStage(BaseModel):
    """A single stage in an ExecutiveProject workflow."""

    stage_id: str
    title: str
    kind: StageKind = StageKind.CUSTOM
    description: str = ""

    # Prompt template with substitution vars:
    # {goal}, {previous_output}, {context}, {iteration},
    # {stage_title}, {stage_description}, {expected_output}
    prompt_template: str

    # Execution config
    agent_id: str | None = None
    model_name: str | None = None
    mode: Literal["standard", "pro", "ultra"] = "standard"
    thinking_enabled: bool = False
    subagent_enabled: bool = False

    # Checkpoint config
    checkpoint_before: bool = False
    checkpoint_after: bool = True

    # Input chaining — list of stage_ids whose latest output feeds this stage
    input_from: list[str] = Field(default_factory=list)
    expected_output: str | None = None

    # Iteration policy
    iteration_policy: IterationPolicy = Field(default_factory=IterationPolicy)

    # Runtime state (mutated during execution)
    status: StageStatus = StageStatus.PENDING
    iteration_count: int = 0
    outputs: list[StageOutput] = Field(default_factory=list)
    current_output: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    def latest_output(self) -> str | None:
        """Return the most recent iteration output text, or None."""
        if self.outputs:
            return self.outputs[-1].output
        return self.current_output


class ProjectCheckpoint(BaseModel):
    """A user-confirmation gate within a project workflow."""

    checkpoint_id: str
    stage_id: str | None = None
    kind: Literal["pre_stage", "post_stage", "iteration", "goal_check"] = "post_stage"
    title: str
    description: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decision_notes: str | None = None


class TerminationCondition(BaseModel):
    """Conditions under which the project should automatically stop."""

    max_duration_minutes: int | None = Field(
        default=None,
        description="Hard time limit. Project marked COMPLETED (or FAILED) after this many minutes.",
    )
    goal_reached_prompt: str | None = Field(
        default=None,
        description="LLM prompt to evaluate goal completion after each stage. "
        "Example: 'Has the report been fully researched, written, and fact-checked to publication standard?'",
    )
    max_total_iterations: int | None = Field(
        default=None,
        description="Maximum total iterations across all stages. Prevents runaway loops.",
    )


class ExecutiveProject(BaseModel):
    """A persistent multi-stage orchestration project managed by the Executive Agent."""

    project_id: str
    title: str
    goal: str = Field(description="The overarching objective this project is steering toward.")

    stages: list[WorkflowStage]
    termination: TerminationCondition = Field(default_factory=TerminationCondition)

    # Runtime state
    status: ProjectStatus = ProjectStatus.PLANNING
    current_stage_index: int = 0
    total_iterations: int = 0
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Shared key-value context passed between all stages.",
    )

    # Timeline
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deadline: datetime | None = None

    # Checkpoint queue
    checkpoints: list[ProjectCheckpoint] = Field(default_factory=list)

    # Metadata
    created_by: str = "executive-agent"

    def current_stage(self) -> WorkflowStage | None:
        if 0 <= self.current_stage_index < len(self.stages):
            return self.stages[self.current_stage_index]
        return None

    def pending_checkpoint(self) -> ProjectCheckpoint | None:
        """Return first pending checkpoint, or None."""
        for cp in self.checkpoints:
            if cp.status == "pending":
                return cp
        return None

    def stage_by_id(self, stage_id: str) -> WorkflowStage | None:
        for s in self.stages:
            if s.stage_id == stage_id:
                return s
        return None

    def collected_outputs(self) -> dict[str, str]:
        """Return {stage_id: latest_output} for all completed stages with output."""
        return {
            s.stage_id: s.latest_output()
            for s in self.stages
            if s.latest_output() is not None
        }

    def summary_dict(self) -> dict[str, Any]:
        """Compact summary for tool responses and API listings."""
        stage = self.current_stage()
        return {
            "project_id": self.project_id,
            "title": self.title,
            "status": self.status.value,
            "current_stage": stage.title if stage else None,
            "current_stage_index": self.current_stage_index,
            "total_stages": len(self.stages),
            "total_iterations": self.total_iterations,
            "pending_checkpoint": (
                self.pending_checkpoint().checkpoint_id
                if self.pending_checkpoint()
                else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ─── Request / response models used by gateway router ────────────────────────


class CreateProjectRequest(BaseModel):
    title: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=5)
    stages: list[dict[str, Any]] = Field(..., min_length=1)
    options: dict[str, Any] = Field(default_factory=dict)


class AdvanceProjectResponse(BaseModel):
    project_id: str
    status: str
    stage_id: str | None = None
    stage_title: str | None = None
    iteration: int | None = None
    checkpoint_id: str | None = None
    message: str = ""


class IterateStageRequest(BaseModel):
    instruction: str = ""


class ApproveCheckpointRequest(BaseModel):
    notes: str = ""
