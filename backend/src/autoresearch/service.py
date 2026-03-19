from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import time

from src.autoresearch.benchmarks import get_benchmark_specs, list_benchmarks
from src.autoresearch.evaluator import evaluate_candidate_record
from src.autoresearch.models import CandidateRecord, CandidateScore, ChampionVersion, ExperimentRecord, ExperimentSummary
from src.autoresearch.optimizer import generate_prompt_mutations
from src.autoresearch.prompts import ensure_default_champions, get_effective_prompt, list_prompt_champions
from src.autoresearch.storage import (
    create_experiment,
    get_candidate,
    get_champion,
    get_experiment,
    list_candidates,
    list_experiments,
    new_candidate_id,
    new_experiment_id,
    save_candidate,
    save_champion,
    update_experiment,
)
from src.autoresearch.ui_design import (
    build_renderable_html,
    build_ui_design_score,
    mutate_ui_candidate,
    render_candidate_html,
    run_vlm_critic,
    screenshot_exists,
)
from src.autoresearch.workflow_routes import (
    deserialize_workflow_definition,
    execute_workflow_definition,
    get_workflow_template,
    list_workflow_templates,
    mutate_workflow_definition,
    score_workflow_candidate,
    serialize_workflow_definition,
    summarize_candidate_metadata,
    workflow_summary_text,
)

def list_experiment_summaries(limit: int = 50) -> list[ExperimentSummary]:
    """List all experiment summaries with candidate counts and top scores.

    Args:
        limit: Maximum number of experiments to return (default: 50).

    Returns:
        List of experiment summaries sorted by creation time.
    """
    summaries: list[ExperimentSummary] = []
    for experiment in list_experiments(limit=limit):
        candidates = list_candidates(experiment.experiment_id)
        top_score = max((candidate.score.composite for candidate in candidates if candidate.score is not None), default=None)
        summaries.append(
            ExperimentSummary(
                experiment_id=experiment.experiment_id,
                domain=experiment.domain,
                role=experiment.role,
                title=experiment.title,
                status=experiment.status,
                promotion_status=experiment.promotion_status,
                champion_version=experiment.champion_version,
                candidate_count=len(candidates),
                top_score=top_score,
                updated_at=experiment.updated_at,
            )
        )
    return summaries


def get_registry_payload() -> dict:
    """Get the autoresearch registry with all available roles and workflow templates.

    Returns:
        Dict with 'roles', 'champions', and 'workflow_templates' for UI initialization.
    """
    champions = list_prompt_champions()
    workflow_templates = []
    for template in list_workflow_templates():
        champion = get_champion(f"workflow-route:{template['template_id']}")
        workflow_templates.append(
            {
                **template,
                "champion_version": champion.version if champion else 1,
                "has_promoted_variant": champion is not None,
            }
        )
    return {
        "manual_start_required": True,
        "approval_required": True,
        "scheduler_enabled": False,
        "domains_enabled": ["subagent_prompt", "workflow_route", "ui_design"],
        "roles": [champion.role for champion in champions],
        "champions": [champion.model_dump(mode="json") for champion in champions],
        "workflow_templates": workflow_templates,
    }


def create_prompt_experiment(
    role: str,
    title: str | None = None,
    notes: str | None = None,
    *,
    max_mutations: int = 3,
    benchmark_limit: int | None = None,
) -> dict:
    """Create a new prompt optimization experiment for a given role.

    Args:
        role: Target role (e.g., 'subagent_prompt:general_purpose').
        title: Experiment title (optional).
        notes: Additional context (optional).
        max_mutations: Number of prompt mutations to generate (1-5, default: 3).
        benchmark_limit: Max benchmark cases to use (optional).

    Returns:
        Dict with 'experiment_id', 'champion_version', and 'candidates'.

    Raises:
        ValueError: If role is unknown or max_mutations is out of range.
    """
    ensure_default_champions()
    champion = get_champion(role)
    if champion is None:
        raise ValueError(f"Unknown prompt role '{role}'.")
    benchmark_specs = get_benchmark_specs(role, limit=benchmark_limit)
    if not benchmark_specs:
        raise ValueError(f"No benchmark cases are configured for role '{role}'.")
    benchmarks = [spec.case for spec in benchmark_specs]
    experiment = ExperimentRecord(
        experiment_id=new_experiment_id(),
        domain="subagent_prompt",
        role=role,
        title=title or f"{role} prompt experiment",
        status="running",
        champion_version=champion.version,
        champion_prompt=champion.prompt_text,
        candidate_ids=[],
        benchmark_case_ids=[case.case_id for case in benchmarks],
        promotion_status="none",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={"max_mutations": max_mutations, "benchmark_limit": len(benchmark_specs)},
        notes=notes,
    )
    create_experiment(experiment)

    champion_candidate = CandidateRecord(
        candidate_id=new_candidate_id(),
        experiment_id=experiment.experiment_id,
        role=role,
        prompt_text=champion.prompt_text,
        source="champion",
        benchmark_case_ids=experiment.benchmark_case_ids,
    )
    champion_candidate = evaluate_candidate_record(champion_candidate, benchmark_limit=len(benchmark_specs))
    save_candidate(champion_candidate)
    experiment.candidate_ids.append(champion_candidate.candidate_id)

    mutations = generate_prompt_mutations(
        role=role,
        champion_prompt=champion.prompt_text,
        benchmark_feedback=champion_candidate.metadata.get("benchmark_feedback", ""),
        count=max_mutations,
    )
    for mutation in mutations:
        candidate = CandidateRecord(
            candidate_id=new_candidate_id(),
            experiment_id=experiment.experiment_id,
            role=role,
            prompt_text=mutation["prompt_text"],
            source="mutation",
            benchmark_case_ids=experiment.benchmark_case_ids,
            metadata={"mutation_strategy": mutation.get("strategy", "mutation")},
        )
        candidate = evaluate_candidate_record(candidate, benchmark_limit=len(benchmark_specs))
        save_candidate(candidate)
        experiment.candidate_ids.append(candidate.candidate_id)

    candidates = list_candidates(experiment.experiment_id)
    scored_candidates = [item for item in candidates if item.score is not None and item.source != "champion"]
    champion_candidates = [item for item in candidates if item.source == "champion" and item.score is not None]
    champion_score = champion_candidates[0].score.composite if champion_candidates and champion_candidates[0].score else 0.0
    experiment.status = "evaluated"
    experiment.promotion_status = "none"
    if scored_candidates:
        top_candidate = max(scored_candidates, key=lambda item: item.score.composite if item.score else -1)
        experiment.metadata["best_candidate_id"] = top_candidate.candidate_id
        experiment.metadata["best_candidate_score"] = top_candidate.score.composite if top_candidate.score else None
        experiment.metadata["champion_score"] = champion_score
        if top_candidate.score and top_candidate.score.composite > champion_score + 0.03:
            experiment.status = "awaiting_approval"
            experiment.promotion_status = "awaiting_approval"
    experiment.updated_at = datetime.now(UTC)
    update_experiment(experiment)
    return get_experiment_detail(experiment.experiment_id)


def get_experiment_detail(experiment_id: str) -> dict:
    """Fetch detailed experiment record with all candidates and scores.

    Args:
        experiment_id: Experiment ID.

    Returns:
        Dict with experiment record and full candidate list.

    Raises:
        ValueError: If experiment not found.
    """
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise ValueError(f"Unknown experiment '{experiment_id}'.")
    candidates_payload: list[dict] = []
    for candidate in list_candidates(experiment_id):
        payload = candidate.model_dump(mode="json")
        if experiment.domain == "ui_design" and screenshot_exists(experiment_id, candidate.candidate_id):
            payload.setdefault("metadata", {})
            payload["metadata"]["screenshot_url"] = f"/api/autoresearch/experiments/{experiment_id}/candidates/{candidate.candidate_id}/screenshot"
        candidates_payload.append(payload)
    return {
        "experiment": experiment.model_dump(mode="json"),
        "benchmarks": [case.model_dump(mode="json") for case in list_benchmarks(experiment.role)],
        "candidates": candidates_payload,
    }


def submit_candidate_score(
    experiment_id: str,
    candidate_id: str,
    *,
    correctness: float,
    efficiency: float,
    speed: float,
    notes: str | None = None,
) -> dict:
    """Score a candidate in an experiment.

    Args:
        experiment_id: Experiment ID.
        candidate_id: Candidate ID.
        correctness: Correctness score (0-1).
        efficiency: Efficiency score (0-1).
        speed: Speed/latency score (0-1).
        notes: Optional scoring notes.

    Returns:
        Dict with updated candidate and composite score.

    Raises:
        ValueError: If candidate or experiment not found.
    """
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise ValueError(f"Unknown experiment '{experiment_id}'.")
    candidate = get_candidate(candidate_id)
    if candidate is None or candidate.experiment_id != experiment_id:
        raise ValueError(f"Candidate '{candidate_id}' does not belong to experiment '{experiment_id}'.")

    composite = round((correctness * 0.7) + (efficiency * 0.2) + (speed * 0.1), 4)
    candidate.score = CandidateScore(
        correctness=correctness,
        efficiency=efficiency,
        speed=speed,
        composite=composite,
        notes=notes,
    )
    save_candidate(candidate)

    candidates = list_candidates(experiment_id)
    scored_candidates = [item for item in candidates if item.score is not None and item.source != "champion"]
    champion_candidates = [item for item in candidates if item.source == "champion" and item.score is not None]

    if scored_candidates:
        experiment.status = "evaluated"
        experiment.updated_at = datetime.now(UTC)
        top_candidate = max(scored_candidates, key=lambda item: item.score.composite if item.score else -1)
        champion_score = champion_candidates[0].score.composite if champion_candidates and champion_candidates[0].score else 0.0
        if top_candidate.score and top_candidate.score.composite > champion_score + 0.03:
            experiment.status = "awaiting_approval"
            experiment.promotion_status = "awaiting_approval"
        update_experiment(experiment)

    return get_experiment_detail(experiment_id)


def approve_experiment(experiment_id: str, approved_by: str = "executive") -> dict:
    """Approve and promote a candidate to champion.

    Args:
        experiment_id: Experiment ID.
        approved_by: User ID approving (default: 'executive').

    Returns:
        Dict with updated experiment and new champion version.

    Raises:
        ValueError: If experiment has no scored candidates.
    """
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise ValueError(f"Unknown experiment '{experiment_id}'.")
    candidates = list_candidates(experiment_id)
    scored = [item for item in candidates if item.score is not None and item.source != "champion"]
    if not scored:
        raise ValueError("No scored mutation candidates are available for promotion.")
    winner = max(scored, key=lambda item: item.score.composite if item.score else -1)

    if experiment.domain == "workflow_route":
        template_id = experiment.role
        champion_role = f"workflow-route:{template_id}"
        prior = get_champion(champion_role)
        next_version = (prior.version if prior else 0) + 1
        save_champion(
            ChampionVersion(
                role=champion_role,
                prompt_text=winner.prompt_text,
                version=next_version,
                source_candidate_id=winner.candidate_id,
                updated_at=datetime.now(UTC),
                promoted_by=approved_by,
            )
        )
        winner.promoted_at = datetime.now(UTC)
        save_candidate(winner)
        experiment.status = "promoted"
        experiment.promotion_status = "approved"
        experiment.updated_at = datetime.now(UTC)
        experiment.metadata["promoted_candidate_id"] = winner.candidate_id
        experiment.metadata["promoted_template_id"] = template_id
        update_experiment(experiment)
        return get_experiment_detail(experiment_id)

    prior = get_champion(experiment.role)
    next_version = (prior.version if prior else 0) + 1
    save_champion(
        ChampionVersion(
            role=experiment.role,
            prompt_text=winner.prompt_text,
            version=next_version,
            source_candidate_id=winner.candidate_id,
            updated_at=datetime.now(UTC),
            promoted_by=approved_by,
        )
    )
    winner.promoted_at = datetime.now(UTC)
    save_candidate(winner)
    experiment.status = "promoted"
    experiment.promotion_status = "approved"
    experiment.updated_at = datetime.now(UTC)
    update_experiment(experiment)
    return get_experiment_detail(experiment_id)


def reject_experiment(experiment_id: str, reason: str | None = None) -> dict:
    """Reject an experiment and its candidates.

    Args:
        experiment_id: Experiment ID.
        reason: Optional rejection reason.

    Returns:
        Dict with updated experiment status.

    Raises:
        ValueError: If experiment not found.
    """
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise ValueError(f"Unknown experiment '{experiment_id}'.")
    experiment.status = "rejected"
    experiment.promotion_status = "rejected"
    experiment.last_error = reason
    experiment.updated_at = datetime.now(UTC)
    update_experiment(experiment)
    return get_experiment_detail(experiment_id)


def rollback_role_prompt(role: str, prompt_text: str, actor_id: str = "executive") -> ChampionVersion:
    """Rollback to a specific prompt version for a role.

    Args:
        role: Target role.
        prompt_text: Prompt text to restore.
        actor_id: User ID performing rollback (default: 'executive').

    Returns:
        New champion version record.
    """
    prior = get_champion(role)
    next_version = (prior.version if prior else 0) + 1
    return save_champion(
        ChampionVersion(
            role=role,
            prompt_text=prompt_text,
            version=next_version,
            source_candidate_id=None,
            updated_at=datetime.now(UTC),
            promoted_by=actor_id,
        )
    )


def stop_experiment(experiment_id: str, reason: str | None = None) -> dict:
    """Stop a running experiment.

    Args:
        experiment_id: Experiment ID.
        reason: Optional reason for stopping.

    Returns:
        Dict with updated experiment status.

    Raises:
        ValueError: If experiment not found.
    """
    experiment = get_experiment(experiment_id)
    if experiment is None:
        raise ValueError(f"Unknown experiment '{experiment_id}'.")
    experiment.status = "stopped"
    experiment.last_error = reason
    experiment.updated_at = datetime.now(UTC)
    update_experiment(experiment)
    return get_experiment_detail(experiment_id)


def get_candidate_screenshot_path(experiment_id: str, candidate_id: str) -> Path:
    """Get the filesystem path for a UI design candidate screenshot.

    Args:
        experiment_id: Experiment ID.
        candidate_id: Candidate ID.

    Returns:
        Path object (may not exist).

    Raises:
        ValueError: If experiment not found or not a UI design experiment.
    """
    experiment = get_experiment(experiment_id)
    if experiment is None or experiment.domain != "ui_design":
        raise ValueError(f"Unknown UI design experiment '{experiment_id}'.")
    candidate = get_candidate(candidate_id)
    if candidate is None or candidate.experiment_id != experiment_id:
        raise ValueError(f"Candidate '{candidate_id}' does not belong to experiment '{experiment_id}'.")
    screenshot_url = candidate.metadata.get("screenshot_url")
    if screenshot_url is None and not screenshot_exists(experiment_id, candidate_id):
        raise ValueError("No screenshot is available for this candidate.")
    from src.autoresearch.ui_design import screenshot_path_for

    path = screenshot_path_for(experiment_id, candidate_id)
    if not path.exists():
        raise ValueError("No screenshot is available for this candidate.")
    return path


def create_ui_design_experiment(
    *,
    prompt: str,
    component_code: str,
    title: str | None = None,
    max_iterations: int = 3,
) -> dict:
    """Create a UI design optimization experiment.

    Args:
        prompt: Mutation prompt for VLM to critique and improve component.
        component_code: React component code to optimize.
        title: Experiment title (optional).
        max_iterations: Max design iterations (1-3, default: 3).

    Returns:
        Dict with 'experiment_id' and initial 'candidates'.
    """
    max_iterations = max(1, min(max_iterations, 3))
    experiment = ExperimentRecord(
        experiment_id=new_experiment_id(),
        domain="ui_design",
        role="ui-design",
        title=title or "UI design optimization",
        status="running",
        champion_version=0,
        champion_prompt=component_code,
        candidate_ids=[],
        benchmark_case_ids=[case.case_id for case in list_benchmarks("ui-design")],
        promotion_status="none",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={"prompt": prompt, "max_iterations": max_iterations},
    )
    create_experiment(experiment)

    baseline_html = build_renderable_html(component_code, title=experiment.title, prompt=prompt)
    baseline_candidate = CandidateRecord(
        candidate_id=new_candidate_id(),
        experiment_id=experiment.experiment_id,
        role=experiment.role,
        prompt_text=baseline_html,
        source="manual",
        benchmark_case_ids=experiment.benchmark_case_ids,
        metadata={"iteration": 0, "candidate_kind": "baseline"},
    )

    experiment.candidate_ids.append(baseline_candidate.candidate_id)
    baseline_score = _evaluate_ui_design_candidate(
        experiment_id=experiment.experiment_id,
        candidate=baseline_candidate,
        prompt=prompt,
        baseline_length=len(baseline_html),
    )
    save_candidate(baseline_score)

    best_candidate = baseline_score
    for iteration in range(1, max_iterations + 1):
        improved_html, mutator_mode = mutate_ui_candidate(
            prompt=prompt,
            html=best_candidate.prompt_text,
            critique=best_candidate.metadata.get("critique", {}),
            iteration=iteration,
        )
        candidate = CandidateRecord(
            candidate_id=new_candidate_id(),
            experiment_id=experiment.experiment_id,
            role=experiment.role,
            prompt_text=improved_html,
            source="mutation",
            benchmark_case_ids=experiment.benchmark_case_ids,
            metadata={
                "iteration": iteration,
                "candidate_kind": "mutation",
                "mutator_mode": mutator_mode,
                "parent_candidate_id": best_candidate.candidate_id,
            },
        )
        experiment.candidate_ids.append(candidate.candidate_id)
        candidate = _evaluate_ui_design_candidate(
            experiment_id=experiment.experiment_id,
            candidate=candidate,
            prompt=prompt,
            baseline_length=len(baseline_html),
        )
        save_candidate(candidate)
        if candidate.score and best_candidate.score and candidate.score.composite >= best_candidate.score.composite:
            best_candidate = candidate
        if candidate.metadata.get("visual_score", 0) >= 8:
            break

    experiment.status = "evaluated"
    experiment.updated_at = datetime.now(UTC)
    experiment.metadata["best_candidate_id"] = best_candidate.candidate_id
    update_experiment(experiment)
    return get_experiment_detail(experiment.experiment_id)


def create_workflow_route_experiment(
    *,
    template_id: str,
    title: str | None = None,
    max_mutations: int = 3,
) -> dict:
    """Create a workflow route optimization experiment.

    Args:
        template_id: Workflow template ID.
        title: Experiment title (optional).
        max_mutations: Max route mutations (1-5, default: 3).

    Returns:
        Dict with 'experiment_id' and initial 'candidates'.
    """
    max_mutations = max(1, min(max_mutations, 5))
    baseline_workflow = get_workflow_template(template_id)
    champion_role = f"workflow-route:{template_id}"
    champion = get_champion(champion_role)
    if champion is not None:
        baseline_workflow = deserialize_workflow_definition(champion.prompt_text)

    benchmark_role = champion_role
    experiment = ExperimentRecord(
        experiment_id=new_experiment_id(),
        domain="workflow_route",
        role=template_id,
        title=title or f"{baseline_workflow.title} optimization",
        status="running",
        champion_version=champion.version if champion else 1,
        champion_prompt=serialize_workflow_definition(baseline_workflow),
        candidate_ids=[],
        benchmark_case_ids=[case.case_id for case in list_benchmarks(benchmark_role)],
        promotion_status="none",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={
            "template_id": template_id,
            "benchmark_role": benchmark_role,
            "max_mutations": max_mutations,
            "bandit_ready": False,
            "live_routing_enabled": False,
        },
    )
    create_experiment(experiment)

    baseline_run = execute_workflow_definition(baseline_workflow)
    baseline_score = score_workflow_candidate(baseline=baseline_run, candidate=baseline_run)
    baseline_candidate = CandidateRecord(
        candidate_id=new_candidate_id(),
        experiment_id=experiment.experiment_id,
        role=template_id,
        prompt_text=workflow_summary_text(
            baseline_workflow,
            summarize_candidate_metadata(
                workflow=baseline_workflow,
                baseline_run=baseline_run,
                candidate_run=baseline_run,
                mutations=[],
            ),
        ),
        source="champion",
        benchmark_case_ids=experiment.benchmark_case_ids,
        metadata={
            **summarize_candidate_metadata(
                workflow=baseline_workflow,
                baseline_run=baseline_run,
                candidate_run=baseline_run,
                mutations=[],
            ),
            "candidate_kind": "baseline",
            "workflow_definition": baseline_workflow.model_dump(mode="json"),
        },
        score=CandidateScore(
            correctness=float(baseline_score["correctness"]),
            efficiency=float(baseline_score["efficiency"]),
            speed=float(baseline_score["speed"]),
            composite=float(baseline_score["composite"]),
            notes="Baseline workflow route",
        ),
    )
    save_candidate(baseline_candidate)
    experiment.candidate_ids.append(baseline_candidate.candidate_id)

    best_candidate_score = baseline_candidate.score.composite if baseline_candidate.score else 0.0
    for iteration in range(1, max_mutations + 1):
        mutated_workflow, mutations = mutate_workflow_definition(baseline_workflow, iteration)
        candidate_run = execute_workflow_definition(mutated_workflow)
        candidate_score = score_workflow_candidate(baseline=baseline_run, candidate=candidate_run)
        candidate = CandidateRecord(
            candidate_id=new_candidate_id(),
            experiment_id=experiment.experiment_id,
            role=template_id,
            prompt_text=workflow_summary_text(
                mutated_workflow,
                summarize_candidate_metadata(
                    workflow=mutated_workflow,
                    baseline_run=baseline_run,
                    candidate_run=candidate_run,
                    mutations=mutations,
                ),
            ),
            source="mutation",
            benchmark_case_ids=experiment.benchmark_case_ids,
            metadata={
                **summarize_candidate_metadata(
                    workflow=mutated_workflow,
                    baseline_run=baseline_run,
                    candidate_run=candidate_run,
                    mutations=mutations,
                ),
                "candidate_kind": "mutation",
                "iteration": iteration,
                "workflow_definition": mutated_workflow.model_dump(mode="json"),
            },
            score=CandidateScore(
                correctness=float(candidate_score["correctness"]),
                efficiency=float(candidate_score["efficiency"]),
                speed=float(candidate_score["speed"]),
                composite=float(candidate_score["composite"]),
                notes="Quality-gated workflow route score",
            ),
        )
        save_candidate(candidate)
        experiment.candidate_ids.append(candidate.candidate_id)
        if candidate.score and candidate.score.composite > best_candidate_score:
            best_candidate_score = candidate.score.composite
            experiment.metadata["best_candidate_id"] = candidate.candidate_id

    experiment.status = "evaluated"
    if best_candidate_score > (baseline_candidate.score.composite if baseline_candidate.score else 0.0) + 0.03:
        experiment.status = "awaiting_approval"
        experiment.promotion_status = "awaiting_approval"
    experiment.updated_at = datetime.now(UTC)
    update_experiment(experiment)
    return get_experiment_detail(experiment.experiment_id)


def _evaluate_ui_design_candidate(
    *,
    experiment_id: str,
    candidate: CandidateRecord,
    prompt: str,
    baseline_length: int,
) -> CandidateRecord:
    from src.autoresearch.ui_design import _heuristic_ui_critique
    started_at = time.perf_counter()
    screenshot_path = None
    try:
        _, screenshot_path = render_candidate_html(experiment_id, candidate.candidate_id, candidate.prompt_text)
    except RuntimeError:
        # Renderer not available (pnpm/Playwright missing) — fall back to heuristic
        pass
    if screenshot_path is not None and screenshot_path.exists():
        critique = run_vlm_critic(prompt, candidate.prompt_text, screenshot_path)
    else:
        critique = _heuristic_ui_critique(prompt, candidate.prompt_text)
    elapsed = time.perf_counter() - started_at
    visual_score = float(critique.get("score", 0))
    candidate.score = build_ui_design_score(
        visual_score=visual_score,
        elapsed_seconds=elapsed,
        baseline_length=baseline_length,
        candidate_length=len(candidate.prompt_text),
        critique=critique,
    )
    candidate.metadata.update(
        {
            "render_time_seconds": round(elapsed, 3),
            "visual_score": visual_score,
            "critique": critique,
        }
    )
    return candidate
