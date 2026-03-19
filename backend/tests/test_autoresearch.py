from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.autoresearch.models import BenchmarkCase, CandidateRecord, CandidateScore, ExperimentRecord
from src.autoresearch.prompts import register_prompt_defaults
from src.autoresearch.service import (
    approve_experiment,
    create_prompt_experiment,
    create_ui_design_experiment,
    create_workflow_route_experiment,
    get_candidate_screenshot_path,
    get_experiment_detail,
    get_registry_payload,
    list_experiment_summaries,
    reject_experiment,
    rollback_role_prompt,
    stop_experiment,
    submit_candidate_score,
)
from src.autoresearch.storage import get_candidate, get_champion, get_experiment, save_candidate, save_champion
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


def test_reject_experiment_updates_status(monkeypatch, tmp_path: Path):
    """Test that rejecting an experiment updates status and promotion_status."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))
    register_prompt_defaults({"general-purpose": "You are a general-purpose agent."})
    monkeypatch.setattr(
        "src.autoresearch.service.generate_prompt_mutations",
        lambda **_: [{"prompt_text": "Test", "strategy": "test"}],
    )
    monkeypatch.setattr(
        "src.autoresearch.service.evaluate_candidate_record",
        lambda candidate, **_: (
            setattr(
                candidate,
                "score",
                CandidateScore(correctness=0.8, efficiency=0.8, speed=0.8, composite=0.8),
            ),
            candidate,
        )[1],
    )

    result = create_prompt_experiment("general-purpose")
    experiment_id = result["experiment"]["experiment_id"]

    rejected = reject_experiment(experiment_id, reason="Not suitable")
    assert rejected["experiment"]["status"] == "rejected"
    assert rejected["experiment"]["promotion_status"] == "rejected"
    assert rejected["experiment"]["last_error"] == "Not suitable"


def test_reject_experiment_invalid_id(monkeypatch, tmp_path: Path):
    """Test that rejecting nonexistent experiment raises ValueError."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    with pytest.raises(ValueError, match="Unknown experiment"):
        reject_experiment("nonexistent-id")


def test_rollback_prompt_restores_version(monkeypatch, tmp_path: Path):
    """Test that rollback creates new champion version."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    original = rollback_role_prompt("test-role", "Original prompt")
    assert original.version == 1

    rolled_back = rollback_role_prompt("test-role", "New prompt", actor_id="user123")
    assert rolled_back.version == 2
    assert rolled_back.prompt_text == "New prompt"
    assert rolled_back.promoted_by == "user123"


def test_rollback_prompt_invalid_role(monkeypatch, tmp_path: Path):
    """Test that rollback succeeds even for unknown roles (creates initial version)."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    result = rollback_role_prompt("brand-new-role", "First version")
    assert result.version == 1
    assert result.role == "brand-new-role"


def test_stop_experiment_halts_running(monkeypatch, tmp_path: Path):
    """Test that stopping an experiment changes status to stopped."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))
    register_prompt_defaults({"general-purpose": "You are a general-purpose agent."})
    monkeypatch.setattr(
        "src.autoresearch.service.generate_prompt_mutations",
        lambda **_: [{"prompt_text": "Test", "strategy": "test"}],
    )
    monkeypatch.setattr(
        "src.autoresearch.service.evaluate_candidate_record",
        lambda candidate, **_: (
            setattr(
                candidate,
                "score",
                CandidateScore(correctness=0.5, efficiency=0.5, speed=0.5, composite=0.5),
            ),
            candidate,
        )[1],
    )

    result = create_prompt_experiment("general-purpose", max_mutations=1)
    experiment_id = result["experiment"]["experiment_id"]

    stopped = stop_experiment(experiment_id, reason="User cancelled")
    assert stopped["experiment"]["status"] == "stopped"
    assert stopped["experiment"]["last_error"] == "User cancelled"


def test_stop_experiment_idempotent(monkeypatch, tmp_path: Path):
    """Test that stopping an already stopped experiment doesn't error."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))
    register_prompt_defaults({"general-purpose": "You are a general-purpose agent."})
    monkeypatch.setattr(
        "src.autoresearch.service.generate_prompt_mutations",
        lambda **_: [{"prompt_text": "Test", "strategy": "test"}],
    )
    monkeypatch.setattr(
        "src.autoresearch.service.evaluate_candidate_record",
        lambda candidate, **_: (
            setattr(
                candidate,
                "score",
                CandidateScore(correctness=0.5, efficiency=0.5, speed=0.5, composite=0.5),
            ),
            candidate,
        )[1],
    )

    result = create_prompt_experiment("general-purpose", max_mutations=1)
    experiment_id = result["experiment"]["experiment_id"]

    stop_experiment(experiment_id, reason="First stop")
    stopped_twice = stop_experiment(experiment_id, reason="Second stop")
    assert stopped_twice["experiment"]["status"] == "stopped"


def test_approve_with_no_scored_candidates(monkeypatch, tmp_path: Path):
    """Test that approving experiment with no scores raises descriptive error."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    from src.autoresearch.storage import new_experiment_id

    experiment = ExperimentRecord(
        experiment_id=new_experiment_id(),
        domain="subagent_prompt",
        role="test-role",
        title="Empty experiment",
        champion_version=1,
        champion_prompt="Test",
        status="draft",
    )
    from src.autoresearch.storage import create_experiment

    create_experiment(experiment)

    with pytest.raises(ValueError, match="No scored mutation candidates"):
        approve_experiment(experiment.experiment_id)


def test_score_deserialization_edge_cases(monkeypatch, tmp_path: Path):
    """Test that score round-trip preserves all values including edge cases."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    from src.autoresearch.storage import new_candidate_id

    # Test all zeros
    candidate_zeros = CandidateRecord(
        candidate_id=new_candidate_id(),
        experiment_id="test-exp",
        role="test",
        prompt_text="Test",
        score=CandidateScore(correctness=0.0, efficiency=0.0, speed=0.0, composite=0.0),
    )
    save_candidate(candidate_zeros)
    retrieved_zeros = get_candidate(candidate_zeros.candidate_id)
    assert retrieved_zeros.score.correctness == 0.0
    assert retrieved_zeros.score.composite == 0.0

    # Test all ones
    candidate_ones = CandidateRecord(
        candidate_id=new_candidate_id(),
        experiment_id="test-exp",
        role="test",
        prompt_text="Test",
        score=CandidateScore(correctness=1.0, efficiency=1.0, speed=1.0, composite=1.0),
    )
    save_candidate(candidate_ones)
    retrieved_ones = get_candidate(candidate_ones.candidate_id)
    assert retrieved_ones.score.correctness == 1.0

    # Test with notes
    candidate_notes = CandidateRecord(
        candidate_id=new_candidate_id(),
        experiment_id="test-exp",
        role="test",
        prompt_text="Test",
        score=CandidateScore(
            correctness=0.5,
            efficiency=0.5,
            speed=0.5,
            composite=0.5,
            notes="Some notes",
        ),
    )
    save_candidate(candidate_notes)
    retrieved_notes = get_candidate(candidate_notes.candidate_id)
    assert retrieved_notes.score.notes == "Some notes"


def test_datetime_tz_aware_storage(monkeypatch, tmp_path: Path):
    """Test that datetime values are stored and retrieved with UTC timezone."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    from src.autoresearch.storage import new_candidate_id

    now = datetime.now(UTC)
    candidate = CandidateRecord(
        candidate_id=new_candidate_id(),
        experiment_id="test-exp",
        role="test",
        prompt_text="Test",
        created_at=now,
        promoted_at=now,
    )
    save_candidate(candidate)
    retrieved = get_candidate(candidate.candidate_id)

    assert retrieved.created_at.tzinfo == UTC
    assert retrieved.promoted_at.tzinfo == UTC
    assert retrieved.created_at.replace(microsecond=0) == now.replace(microsecond=0)


def test_candidate_screenshot_nonexistent(monkeypatch, tmp_path: Path):
    """Test that requesting screenshot for nonexistent candidate raises error."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))

    with pytest.raises(ValueError, match="Unknown UI design experiment"):
        get_candidate_screenshot_path("nonexistent-exp", "nonexistent-cand")


def test_experiment_state_transitions_validation(monkeypatch, tmp_path: Path):
    """Test that experiments follow expected status transitions."""
    monkeypatch.setenv("AUTORESEARCH_DB_PATH", str(tmp_path / "autoresearch.db"))
    register_prompt_defaults({"general-purpose": "You are a general-purpose agent."})
    monkeypatch.setattr(
        "src.autoresearch.service.generate_prompt_mutations",
        lambda **_: [{"prompt_text": "Test", "strategy": "test"}],
    )
    monkeypatch.setattr(
        "src.autoresearch.service.evaluate_candidate_record",
        lambda candidate, **_: (
            setattr(
                candidate,
                "score",
                CandidateScore(correctness=0.95, efficiency=0.95, speed=0.95, composite=0.95),
            ),
            candidate,
        )[1],
    )

    result = create_prompt_experiment("general-purpose")
    exp_id = result["experiment"]["experiment_id"]
    assert result["experiment"]["status"] in ("evaluated", "awaiting_approval")

    # Verify we can approve the experiment and it transitions to promoted
    approved = approve_experiment(exp_id)
    assert approved["experiment"]["status"] == "promoted"
    assert approved["experiment"]["promotion_status"] == "approved"

    # Verify the champion was updated
    reloaded = get_experiment_detail(exp_id)
    assert reloaded["experiment"]["promotion_status"] == "approved"
