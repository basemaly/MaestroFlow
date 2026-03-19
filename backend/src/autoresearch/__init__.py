"""Autoresearch experiment platform.

Three optimization domains:
  - subagent_prompt: Prompt mutations evaluated against benchmark cases.
  - workflow_route: DAG routing mutations scored by cost/latency/fitness.
  - ui_design: Component renders critiqued by VLM and iterated visually.

Experiments are manual-start only. Promotion requires explicit Executive approval.

Public API (import directly from submodules to avoid circular imports):
  - src.autoresearch.models — data models and TypedDicts
  - src.autoresearch.service — experiment lifecycle operations
  - src.autoresearch.storage — persistent storage layer
  - src.autoresearch.benchmarks — benchmark case library
"""

# Lightweight models are safe to import at package level
from src.autoresearch.models import (
    BenchmarkCase,
    BenchmarkRunResult,
    CandidateRecord,
    CandidateScore,
    ChampionVersion,
    ExperimentDomain,
    ExperimentMetadata,
    ExperimentRecord,
    ExperimentStatus,
    ExperimentSummary,
    PromotionStatus,
    PromptExperimentMetadata,
    UiDesignExperimentMetadata,
    WorkflowRouteExperimentMetadata,
)

__all__ = [
    # Models
    "BenchmarkCase",
    "BenchmarkRunResult",
    "CandidateRecord",
    "CandidateScore",
    "ChampionVersion",
    "ExperimentDomain",
    "ExperimentMetadata",
    "ExperimentRecord",
    "ExperimentStatus",
    "ExperimentSummary",
    "PromotionStatus",
    "PromptExperimentMetadata",
    "UiDesignExperimentMetadata",
    "WorkflowRouteExperimentMetadata",
    # Service functions (import from src.autoresearch.service directly)
    "approve_experiment",
    "create_prompt_experiment",
    "create_ui_design_experiment",
    "create_workflow_route_experiment",
    "get_candidate_screenshot_path",
    "get_experiment_detail",
    "get_registry_payload",
    "list_experiment_summaries",
    "reject_experiment",
    "rollback_role_prompt",
    "stop_experiment",
    "submit_candidate_score",
]
