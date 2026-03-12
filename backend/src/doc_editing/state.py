"""State schemas for the document editing graph."""

import operator
from typing import Annotated, Literal, NotRequired, TypedDict


class VersionRecord(TypedDict):
    """A single edited document variant produced by a skill."""

    version_id: str
    skill_name: str
    subagent_type: str
    requested_model: str | None
    output: str
    score: float
    quality_dims: dict[str, float]
    token_count: int
    latency_ms: int
    file_path: str
    model_name: str


class DocEditState(TypedDict):
    """State shared across the doc-edit LangGraph."""

    document: str
    skills: list[str]
    model_location: Literal["local", "remote", "mixed"]
    model_strength: Literal["fast", "cheap", "strong"]
    preferred_model: str | None
    selected_models: list[str] | list[tuple[str | None, str | None]]
    token_budget: int
    run_id: str
    run_dir: str
    versions: Annotated[list[VersionRecord], operator.add]
    ranked_versions: NotRequired[list[VersionRecord]]
    tokens_used: NotRequired[int]
    selected_version: NotRequired[VersionRecord | None]
    final_path: NotRequired[str | None]
    review_payload: NotRequired[dict]
    current_skill: NotRequired[str]
    current_skill_index: NotRequired[int]
    current_model_name: NotRequired[str]
    current_model_request: NotRequired[str | None]
