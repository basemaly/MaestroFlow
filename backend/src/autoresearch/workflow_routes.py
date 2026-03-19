from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from graphlib import TopologicalSorter
from typing import Any

from pydantic import BaseModel, Field

from src.integrations.browser_runtime.service import select_browser_runtime
from src.integrations.stateweave import create_state_snapshot, diff_state_snapshots
from src.models.routing import first_configured_model


class WorkflowNodeDefinition(BaseModel):
    node_id: str
    title: str
    kind: str
    model: str
    depends_on: list[str] = Field(default_factory=list)
    workload: float = Field(default=1.0, ge=0.2, le=5.0)
    required_capabilities: list[str] = Field(default_factory=list)
    output_keys: list[str] = Field(default_factory=list)
    parallel_safe: bool = False


class WorkflowDefinition(BaseModel):
    template_id: str
    title: str
    objective: str
    description: str
    required_outputs: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)
    quality_bar: float = Field(default=0.72, ge=0, le=1)
    nodes: list[WorkflowNodeDefinition]


class NodeTelemetry(BaseModel):
    node_id: str
    title: str
    kind: str
    model: str
    runtime: str | None = None
    runtime_fallback_from: str | None = None
    started_at_ms: int
    finished_at_ms: int
    duration_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    quality_score: float
    dependency_depth: int


class WorkflowRunResult(BaseModel):
    wall_time_ms: int
    critical_path_ms: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    quality_score: float
    passed_quality_gate: bool
    coverage_score: float
    fact_retention_score: float
    node_telemetry: list[NodeTelemetry]
    quality_notes: list[str] = Field(default_factory=list)


class WorkflowMutation(BaseModel):
    kind: str
    description: str
    target_node_ids: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _ModelProfile:
    speed_factor: float
    quality_factor: float
    input_rate: float
    output_rate: float


_FAST_KEYWORDS = ("flash", "haiku", "mini", "lite", "small", "7b", "8b", "codex")
_CHEAP_KEYWORDS = ("flash", "haiku", "mini", "lite", "small", "7b", "8b")
_STRONG_KEYWORDS = ("opus", "sonnet", "pro", "gpt-5", "32b", "70b", "72b", "reasoning")
_LOCAL_KEYWORDS = ("qwen", "mistral", "llama", "deepseek", "-lan")


def _resolve_model(candidates: list[str], fallback: str) -> str:
    return first_configured_model(candidates) or fallback


def _node(*, node_id: str, title: str, kind: str, model: str, depends_on: list[str] | None = None,
          workload: float = 1.0, required_capabilities: list[str] | None = None,
          output_keys: list[str] | None = None, parallel_safe: bool = False) -> WorkflowNodeDefinition:
    return WorkflowNodeDefinition(
        node_id=node_id,
        title=title,
        kind=kind,
        model=model,
        depends_on=list(depends_on or []),
        workload=workload,
        required_capabilities=list(required_capabilities or []),
        output_keys=list(output_keys or []),
        parallel_safe=parallel_safe,
    )


_WORKFLOW_TEMPLATES: dict[str, WorkflowDefinition] = {
    "research_report": WorkflowDefinition(
        template_id="research_report",
        title="Research report pipeline",
        objective="Scrape a website, extract the relevant facts, summarize them, and generate a final report.",
        description="A representative multi-stage research workflow with one unnecessary sequential edge that can be optimized away.",
        required_outputs=["source_snapshot", "fact_table", "summary", "report_markdown"],
        required_facts=["pricing", "capabilities", "constraints", "citations"],
        quality_bar=0.74,
        nodes=[
            _node(
                node_id="scrape_site",
                title="Scrape source website",
                kind="retrieval",
                model="browser",
                workload=1.0,
                output_keys=["source_snapshot"],
                parallel_safe=False,
            ),
            _node(
                node_id="extract_facts",
                title="Extract structured facts",
                kind="analysis",
                model="gpt-5",
                depends_on=["scrape_site"],
                workload=1.4,
                required_capabilities=["fact_extraction", "fidelity"],
                output_keys=["fact_table"],
            ),
            _node(
                node_id="prepare_report_shell",
                title="Prepare report shell",
                kind="formatting",
                model="gpt-5-2-mini",
                depends_on=["scrape_site"],
                workload=0.8,
                required_capabilities=["document_structure"],
                output_keys=["outline"],
                parallel_safe=True,
            ),
            _node(
                node_id="summarize_findings",
                title="Summarize findings",
                kind="summarization",
                model="claude-sonnet-4-6",
                depends_on=["extract_facts", "prepare_report_shell"],
                workload=1.2,
                required_capabilities=["synthesis", "coverage"],
                output_keys=["summary"],
            ),
            _node(
                node_id="generate_report",
                title="Generate final report",
                kind="writing",
                model="gpt-5",
                depends_on=["summarize_findings"],
                workload=1.4,
                required_capabilities=["writing", "citation_discipline"],
                output_keys=["report_markdown"],
            ),
        ],
    ),
    "fullstack_feature": WorkflowDefinition(
        template_id="fullstack_feature",
        title="Full-stack feature delivery",
        objective="Plan, implement, and review a full-stack feature spanning API and frontend work.",
        description="A coding workflow with a planning stage followed by API and UI work that can be split into parallel branches.",
        required_outputs=["feature_plan", "api_patch", "ui_patch", "integration_review"],
        required_facts=["acceptance_criteria", "api_contract", "ui_states", "tests"],
        quality_bar=0.76,
        nodes=[
            _node(
                node_id="plan_feature",
                title="Plan feature slice",
                kind="planning",
                model="gpt-5",
                workload=1.1,
                required_capabilities=["planning", "risk_spotting"],
                output_keys=["feature_plan"],
            ),
            _node(
                node_id="implement_api",
                title="Implement backend/API slice",
                kind="coding",
                model="gpt-5-2-codex",
                depends_on=["plan_feature"],
                workload=1.5,
                required_capabilities=["api_contract", "tests"],
                output_keys=["api_patch"],
                parallel_safe=True,
            ),
            _node(
                node_id="implement_ui",
                title="Implement frontend slice",
                kind="coding",
                model="gpt-5-2-codex",
                depends_on=["implement_api"],
                workload=1.5,
                required_capabilities=["ui_states", "component_quality"],
                output_keys=["ui_patch"],
                parallel_safe=True,
            ),
            _node(
                node_id="integration_review",
                title="Integration review and polish",
                kind="review",
                model="claude-sonnet-4-6",
                depends_on=["implement_api", "implement_ui"],
                workload=1.0,
                required_capabilities=["integration", "regression_review"],
                output_keys=["integration_review"],
            ),
        ],
    ),
}


def list_workflow_templates() -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for template in _WORKFLOW_TEMPLATES.values():
        templates.append(
            {
                "template_id": template.template_id,
                "title": template.title,
                "description": template.description,
                "objective": template.objective,
                "required_outputs": template.required_outputs,
                "node_count": len(template.nodes),
            }
        )
    return templates


def get_workflow_template(template_id: str) -> WorkflowDefinition:
    try:
        return deepcopy(_WORKFLOW_TEMPLATES[template_id])
    except KeyError as exc:
        raise ValueError(f"Unknown workflow template '{template_id}'.") from exc


def serialize_workflow_definition(workflow: WorkflowDefinition) -> str:
    return workflow.model_dump_json(indent=2)


def deserialize_workflow_definition(payload: str) -> WorkflowDefinition:
    return WorkflowDefinition.model_validate_json(payload)


def _model_profile(model_name: str, *, task_kind: str) -> _ModelProfile:
    normalized = model_name.lower()
    speed_factor = 1.0
    quality_factor = 0.72
    input_rate = 1.6
    output_rate = 3.2

    if any(keyword in normalized for keyword in _FAST_KEYWORDS):
        speed_factor -= 0.18
        quality_factor -= 0.04
        input_rate -= 0.45
        output_rate -= 0.8
    if any(keyword in normalized for keyword in _CHEAP_KEYWORDS):
        input_rate -= 0.35
        output_rate -= 0.6
    if any(keyword in normalized for keyword in _STRONG_KEYWORDS):
        speed_factor += 0.18
        quality_factor += 0.11
        input_rate += 0.55
        output_rate += 1.15
    if any(keyword in normalized for keyword in _LOCAL_KEYWORDS):
        speed_factor += 0.08
        input_rate -= 0.15
        output_rate -= 0.2
    if model_name == "browser":
        return _ModelProfile(speed_factor=0.95, quality_factor=0.82, input_rate=0.0, output_rate=0.0)
    if task_kind == "coding" and "codex" in normalized:
        quality_factor += 0.08
    if task_kind in {"writing", "summarization"} and any(keyword in normalized for keyword in ("claude", "gemini")):
        quality_factor += 0.05

    return _ModelProfile(
        speed_factor=max(0.55, speed_factor),
        quality_factor=max(0.45, min(0.98, quality_factor)),
        input_rate=max(0.2, input_rate),
        output_rate=max(0.4, output_rate),
    )


def _base_tokens(kind: str, workload: float) -> tuple[int, int]:
    kind_scale = {
        "retrieval": (260, 420),
        "analysis": (620, 260),
        "formatting": (320, 220),
        "summarization": (540, 240),
        "writing": (500, 420),
        "planning": (440, 220),
        "coding": (680, 340),
        "review": (460, 200),
    }.get(kind, (420, 220))
    return int(kind_scale[0] * workload), int(kind_scale[1] * workload)


def _task_affinity(kind: str, model_name: str) -> float:
    normalized = model_name.lower()
    affinity = 0.72
    if kind == "coding" and "codex" in normalized:
        affinity += 0.12
    if kind in {"summarization", "writing"} and any(token in normalized for token in ("claude", "gemini")):
        affinity += 0.08
    if kind == "analysis" and "gpt-5" in normalized:
        affinity += 0.08
    if kind == "review" and any(token in normalized for token in ("claude", "gemini-2-5-pro", "gpt-5")):
        affinity += 0.07
    if kind == "retrieval" and model_name == "browser":
        affinity += 0.12
    return max(0.45, min(0.98, affinity))


def execute_workflow_definition(workflow: WorkflowDefinition, *, browser_runtime: str = "playwright") -> WorkflowRunResult:
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    if len(nodes_by_id) != len(workflow.nodes):
        raise ValueError("Workflow definition contains duplicate node ids.")

    sorter = TopologicalSorter({node.node_id: tuple(node.depends_on) for node in workflow.nodes})
    execution_order = list(sorter.static_order())
    node_results: dict[str, NodeTelemetry] = {}

    for node_id in execution_order:
        node = nodes_by_id[node_id]
        profile = _model_profile(node.model, task_kind=node.kind)
        runtime = None
        runtime_fallback_from = None
        if node.model == "browser":
            runtime_selection = select_browser_runtime(
                prefer_lightpanda=browser_runtime == "lightpanda",
                allow_fallback=True,
            )
            runtime = runtime_selection.runtime
            runtime_fallback_from = runtime_selection.fallback_from
        input_tokens, output_tokens = _base_tokens(node.kind, node.workload)
        duration_ms = int(850 + ((input_tokens + output_tokens) * 0.9) * profile.speed_factor)
        started_at_ms = max((node_results[dep].finished_at_ms for dep in node.depends_on), default=0)
        finished_at_ms = started_at_ms + duration_ms
        dependency_depth = max((node_results[dep].dependency_depth + 1 for dep in node.depends_on), default=0)
        quality_score = round((profile.quality_factor * 0.58) + (_task_affinity(node.kind, node.model) * 0.42), 4)
        cost_usd = round(
            ((input_tokens * profile.input_rate) + (output_tokens * profile.output_rate)) / 1_000_000,
            6,
        )
        node_results[node_id] = NodeTelemetry(
            node_id=node.node_id,
            title=node.title,
            kind=node.kind,
            model=node.model,
            runtime=runtime,
            runtime_fallback_from=runtime_fallback_from,
            started_at_ms=started_at_ms,
            finished_at_ms=finished_at_ms,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
            dependency_depth=dependency_depth,
        )

    telemetry = [node_results[node_id] for node_id in execution_order]
    wall_time_ms = max((node.finished_at_ms for node in telemetry), default=0)
    total_input_tokens = sum(node.input_tokens for node in telemetry)
    total_output_tokens = sum(node.output_tokens for node in telemetry)
    total_cost_usd = round(sum(node.cost_usd for node in telemetry), 6)
    quality_score = round(sum(node.quality_score for node in telemetry) / max(1, len(telemetry)), 4)

    produced_outputs = {output_key for node in workflow.nodes for output_key in node.output_keys}
    covered_outputs = sum(1 for output_key in workflow.required_outputs if output_key in produced_outputs)
    coverage_score = round(covered_outputs / max(1, len(workflow.required_outputs)), 4)

    fact_nodes = [node_results[node.node_id].quality_score for node in workflow.nodes if node.kind in {"analysis", "summarization", "writing", "review"}]
    fact_retention_score = round(sum(fact_nodes) / max(1, len(fact_nodes)), 4)

    quality_notes: list[str] = []
    if coverage_score < 1:
        quality_notes.append("Required outputs are not fully covered by this DAG.")
    if fact_retention_score < workflow.quality_bar:
        quality_notes.append("Fact retention fell below the template quality bar.")
    if any(node.duration_ms > 2500 for node in telemetry):
        quality_notes.append("At least one node dominates the critical path and is a parallelization candidate.")

    passed_quality_gate = coverage_score >= 1 and fact_retention_score >= workflow.quality_bar and quality_score >= workflow.quality_bar
    return WorkflowRunResult(
        wall_time_ms=wall_time_ms,
        critical_path_ms=wall_time_ms,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cost_usd=total_cost_usd,
        quality_score=quality_score,
        passed_quality_gate=passed_quality_gate,
        coverage_score=coverage_score,
        fact_retention_score=fact_retention_score,
        node_telemetry=telemetry,
        quality_notes=quality_notes,
    )


def score_workflow_candidate(
    *,
    baseline: WorkflowRunResult,
    candidate: WorkflowRunResult,
    latency_weight: float = 0.6,
    cost_weight: float = 0.4,
) -> dict[str, float | bool]:
    latency_ratio = baseline.wall_time_ms / max(candidate.wall_time_ms, 1)
    cost_ratio = baseline.total_cost_usd / max(candidate.total_cost_usd, 0.000001)
    speed = round(min(1.0, latency_ratio), 4)
    efficiency = round(min(1.0, cost_ratio), 4)
    correctness = round(candidate.quality_score if candidate.passed_quality_gate else candidate.quality_score * 0.35, 4)
    fitness = 0.0
    composite = 0.0
    if candidate.passed_quality_gate:
        fitness = round((latency_ratio * latency_weight) + (cost_ratio * cost_weight), 4)
        composite = round((speed * 0.4) + (efficiency * 0.35) + (correctness * 0.25), 4)
    return {
        "correctness": correctness,
        "efficiency": efficiency,
        "speed": speed,
        "fitness": fitness,
        "composite": composite,
        "passed_quality_gate": candidate.passed_quality_gate,
    }


def _find_parallelization_target(workflow: WorkflowDefinition) -> WorkflowNodeDefinition | None:
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    for node in workflow.nodes:
        if not node.parallel_safe or len(node.depends_on) != 1:
            continue
        dependency = nodes_by_id[node.depends_on[0]]
        if dependency.kind in {"retrieval", "planning"}:
            return node
    return None


def _swap_model(workflow: WorkflowDefinition, *, preferred_kinds: tuple[str, ...], cheaper: bool) -> WorkflowMutation | None:
    for node in workflow.nodes:
        if node.kind not in preferred_kinds or node.model == "browser":
            continue
        if cheaper:
            candidates = [
                "gemini-2-5-flash",
                "claude-haiku-4-5",
                "gpt-5-2-mini",
                "gpt-4-1-mini",
                "qwen-7b-coder-lan",
            ]
        else:
            candidates = [
                "gpt-5",
                "gemini-2-5-pro",
                "claude-sonnet-4-6",
                "gpt-5-2-codex",
                "qwen-32b-coder-lan",
            ]
        replacement = _resolve_model(candidates, node.model)
        if replacement == node.model:
            continue
        previous = node.model
        node.model = replacement
        return WorkflowMutation(
            kind="model_swap",
            description=f"Swapped node '{node.node_id}' from {previous} to {replacement}.",
            target_node_ids=[node.node_id],
        )
    return None


def mutate_workflow_definition(workflow: WorkflowDefinition, iteration: int) -> tuple[WorkflowDefinition, list[WorkflowMutation]]:
    candidate = deepcopy(workflow)
    mutations: list[WorkflowMutation] = []

    if iteration == 1:
        mutation = _swap_model(candidate, preferred_kinds=("summarization", "writing", "review"), cheaper=True)
        if mutation:
            mutations.append(mutation)
    elif iteration == 2:
        target = _find_parallelization_target(candidate)
        if target is not None:
            prior = list(target.depends_on)
            target.depends_on = []
            mutations.append(
                WorkflowMutation(
                    kind="parallelize",
                    description=f"Removed the non-critical dependency from '{target.node_id}' so it can start in parallel.",
                    target_node_ids=[target.node_id, *prior],
                )
            )
        mutation = _swap_model(candidate, preferred_kinds=("analysis", "planning"), cheaper=True)
        if mutation:
            mutations.append(mutation)
    else:
        mutation = _swap_model(candidate, preferred_kinds=("coding", "analysis", "review"), cheaper=False)
        if mutation:
            mutations.append(mutation)
        target = _find_parallelization_target(candidate)
        if target is not None and target.depends_on:
            prior = list(target.depends_on)
            target.depends_on = []
            mutations.append(
                WorkflowMutation(
                    kind="parallelize",
                    description=f"Detached '{target.node_id}' from {', '.join(prior)} to shorten the critical path.",
                    target_node_ids=[target.node_id, *prior],
                )
            )

    if not mutations:
        mutations.append(
            WorkflowMutation(
                kind="noop",
                description="No safe mutation was available for this workflow definition.",
            )
        )
    return candidate, mutations


def summarize_candidate_metadata(
    *,
    workflow: WorkflowDefinition,
    baseline_run: WorkflowRunResult,
    candidate_run: WorkflowRunResult,
    mutations: list[WorkflowMutation],
) -> dict[str, Any]:
    score = score_workflow_candidate(baseline=baseline_run, candidate=candidate_run)
    return {
        "template_id": workflow.template_id,
        "workflow_title": workflow.title,
        "required_outputs": workflow.required_outputs,
        "mutations": [mutation.model_dump(mode="json") for mutation in mutations],
        "telemetry": {
            "wall_time_ms": candidate_run.wall_time_ms,
            "critical_path_ms": candidate_run.critical_path_ms,
            "total_input_tokens": candidate_run.total_input_tokens,
            "total_output_tokens": candidate_run.total_output_tokens,
            "total_cost_usd": candidate_run.total_cost_usd,
            "node_telemetry": [node.model_dump(mode="json") for node in candidate_run.node_telemetry],
        },
        "baseline_comparison": {
            "baseline_wall_time_ms": baseline_run.wall_time_ms,
            "baseline_cost_usd": baseline_run.total_cost_usd,
            "candidate_wall_time_ms": candidate_run.wall_time_ms,
            "candidate_cost_usd": candidate_run.total_cost_usd,
            "latency_ratio": round(baseline_run.wall_time_ms / max(candidate_run.wall_time_ms, 1), 4),
            "cost_ratio": round(baseline_run.total_cost_usd / max(candidate_run.total_cost_usd, 0.000001), 4),
        },
        "quality_gate": {
            "passed": candidate_run.passed_quality_gate,
            "quality_score": candidate_run.quality_score,
            "coverage_score": candidate_run.coverage_score,
            "fact_retention_score": candidate_run.fact_retention_score,
            "notes": candidate_run.quality_notes,
        },
        "fitness_score": score["fitness"],
        "score_breakdown": score,
    }


def workflow_summary_text(workflow: WorkflowDefinition, metadata: dict[str, Any]) -> str:
    summary = {
        "template_id": workflow.template_id,
        "title": workflow.title,
        "nodes": [
            {
                "node_id": node.node_id,
                "title": node.title,
                "kind": node.kind,
                "model": node.model,
                "depends_on": node.depends_on,
            }
            for node in workflow.nodes
        ],
        "metadata": metadata,
    }
    return json.dumps(summary, indent=2)
