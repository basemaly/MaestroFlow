from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


ExperimentDomain = Literal["subagent_prompt", "workflow_route", "ui_design"]
ExperimentStatus = Literal[
    "draft",
    "running",
    "evaluated",
    "awaiting_approval",
    "promoted",
    "rejected",
    "rolled_back",
    "stopped",
]
PromotionStatus = Literal["none", "awaiting_approval", "approved", "rejected", "rolled_back"]


class BenchmarkCase(BaseModel):
    case_id: str
    role: str
    title: str
    prompt: str
    expected_focus: list[str] = Field(default_factory=list)
    validation_hint: str


class CandidateScore(BaseModel):
    correctness: float = Field(ge=0, le=1)
    efficiency: float = Field(ge=0, le=1)
    speed: float = Field(ge=0, le=1)
    composite: float = Field(ge=0, le=1)
    notes: str | None = None


class BenchmarkRunResult(BaseModel):
    case_id: str
    correctness: float = Field(ge=0, le=1)
    efficiency: float = Field(ge=0, le=1)
    speed: float = Field(ge=0, le=1)
    composite: float = Field(ge=0, le=1)
    elapsed_seconds: float = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    notes: str | None = None


class CandidateRecord(BaseModel):
    candidate_id: str
    experiment_id: str
    role: str
    prompt_text: str
    source: Literal["champion", "mutation", "manual"] = "mutation"
    score: CandidateScore | None = None
    benchmark_case_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
    promoted_at: datetime | None = None


class ChampionVersion(BaseModel):
    role: str
    prompt_text: str
    version: int = 1
    source_candidate_id: str | None = None
    updated_at: datetime = Field(default_factory=_utc_now)
    promoted_by: str = "system"


class ExperimentRecord(BaseModel):
    experiment_id: str
    domain: ExperimentDomain
    role: str
    title: str
    status: ExperimentStatus = "draft"
    champion_version: int
    champion_prompt: str
    candidate_ids: list[str] = Field(default_factory=list)
    benchmark_case_ids: list[str] = Field(default_factory=list)
    promotion_status: PromotionStatus = "none"
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None
    notes: str | None = None


class ExperimentSummary(BaseModel):
    experiment_id: str
    domain: ExperimentDomain
    role: str
    title: str
    status: ExperimentStatus
    promotion_status: PromotionStatus
    champion_version: int
    candidate_count: int
    top_score: float | None = None
    updated_at: datetime
