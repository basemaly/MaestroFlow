from pathlib import Path

from src.autoresearch.models import CandidateScore
from src.autoresearch.prompts import register_prompt_defaults
from src.autoresearch.service import (
    approve_experiment,
    create_prompt_experiment,
    create_ui_design_experiment,
    create_workflow_route_experiment,
    get_candidate_screenshot_path,
    get_registry_payload,
    list_experiment_summaries,
)
from src.autoresearch.ui_design import get_ui_candidate_paths
from src.subagents.registry import get_subagent_config


def test_registry_bootstrap_is_manual_only_and_does_not_create_experiments(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))
    register_prompt_defaults({"general-purpose": "You are a general-purpose subagent."})

    payload = get_registry_payload()

    assert payload["manual_start_required"] is True
    assert payload["approval_required"] is True
    assert payload["scheduler_enabled"] is False
    assert payload["domains_enabled"] == ["subagent_prompt", "workflow_route", "ui_design"]
    assert "general-purpose" in payload["roles"]
    assert any(template["template_id"] == "research_report" for template in payload["workflow_templates"])
    assert list_experiment_summaries() == []


def test_subagent_prompt_resolution_seeds_champion_without_starting_experiment(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    config = get_subagent_config("general-purpose")

    assert config is not None
    assert config.system_prompt
    assert list_experiment_summaries() == []


def test_prompt_experiment_requires_explicit_creation(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))
    register_prompt_defaults({"writing-refiner": "You refine drafts."})
    monkeypatch.setattr(
        "src.autoresearch.service.generate_prompt_mutations",
        lambda **_: [
            {"prompt_text": "You refine drafts.\n\n<test>one</test>", "strategy": "test-one"},
            {"prompt_text": "You refine drafts.\n\n<test>two</test>", "strategy": "test-two"},
        ],
    )

    def fake_evaluate(candidate, *, benchmark_limit=None):
        composite = 0.92 if "two" in candidate.prompt_text else 0.54
        candidate.score = CandidateScore(
            correctness=composite,
            efficiency=composite,
            speed=composite,
            composite=composite,
            notes="synthetic",
        )
        candidate.metadata["benchmark_feedback"] = "synthetic feedback"
        return candidate

    monkeypatch.setattr("src.autoresearch.service.evaluate_candidate_record", fake_evaluate)

    before = list_experiment_summaries()
    created = create_prompt_experiment("writing-refiner")
    after = list_experiment_summaries()

    assert before == []
    assert created["experiment"]["role"] == "writing-refiner"
    assert created["experiment"]["status"] == "awaiting_approval"
    assert any(candidate.get("score") for candidate in created["candidates"])
    assert len(after) == 1


def test_ui_design_experiment_generates_candidates_and_screenshot(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    def fake_render(experiment_id: str, candidate_id: str, html: str):
        html_path, screenshot_path = get_ui_candidate_paths(experiment_id, candidate_id)
        html_path.write_text(html, encoding="utf-8")
        screenshot_path.write_bytes(b"png")
        return html_path, screenshot_path

    def fake_critic(prompt: str, html: str, screenshot_path: Path):
        return {
            "score": 8.4 if "iteration-1" in html else 6.7,
            "strengths": ["Clean structure"],
            "issues": ["Needs stronger CTA"],
            "recommended_changes": ["Push hierarchy harder"],
            "summary": "Looks better.",
            "critic_mode": "heuristic",
        }

    def fake_mutate(prompt: str, html: str, critique: dict, iteration: int):
        return f"{html}\n<!-- iteration-{iteration} -->", "heuristic"

    monkeypatch.setattr("src.autoresearch.service.render_candidate_html", fake_render)
    monkeypatch.setattr("src.autoresearch.service.run_vlm_critic", fake_critic)
    monkeypatch.setattr("src.autoresearch.service.mutate_ui_candidate", fake_mutate)

    result = create_ui_design_experiment(
        prompt="Improve this pricing card",
        component_code="<section class='rounded-xl'><button>Buy</button></section>",
        title="Pricing card polish",
        max_iterations=2,
    )

    assert result["experiment"]["domain"] == "ui_design"
    assert result["experiment"]["status"] == "evaluated"
    assert len(result["candidates"]) == 2
    first_candidate = result["candidates"][0]
    second_candidate = result["candidates"][1]
    assert first_candidate["metadata"]["screenshot_url"].endswith("/screenshot")
    assert second_candidate["metadata"]["visual_score"] == 8.4

    screenshot_path = get_candidate_screenshot_path(
        result["experiment"]["experiment_id"],
        second_candidate["candidate_id"],
    )
    assert screenshot_path.exists()


def test_workflow_route_experiment_generates_scored_candidates(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    result = create_workflow_route_experiment(template_id="research_report", max_mutations=3)

    assert result["experiment"]["domain"] == "workflow_route"
    assert result["experiment"]["role"] == "research_report"
    assert len(result["candidates"]) == 4
    baseline = result["candidates"][0]
    mutation = result["candidates"][1]
    assert baseline["source"] == "champion"
    assert baseline["metadata"]["candidate_kind"] == "baseline"
    assert "workflow_definition" in baseline["metadata"]
    assert mutation["metadata"]["candidate_kind"] == "mutation"
    assert "telemetry" in mutation["metadata"]
    assert "mutations" in mutation["metadata"]
    assert mutation["score"] is not None


def test_workflow_route_approval_promotes_candidate(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    result = create_workflow_route_experiment(template_id="research_report", max_mutations=3)
    experiment_id = result["experiment"]["experiment_id"]
    detail = approve_experiment(experiment_id, approved_by="executive")

    assert detail["experiment"]["status"] == "promoted"
    assert detail["experiment"]["promotion_status"] == "approved"
    promoted = [candidate for candidate in detail["candidates"] if candidate.get("promoted_at")]
    assert promoted
