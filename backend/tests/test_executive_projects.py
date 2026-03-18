"""Unit tests for ExecutiveProject orchestration layer."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Redirect executive SQLite DB to a temp file for each test."""
    db_path = tmp_path / "executive.db"
    os.environ["EXECUTIVE_DB_PATH"] = str(db_path)
    yield db_path
    os.environ.pop("EXECUTIVE_DB_PATH", None)


def _stage_raw(
    stage_id: str,
    title: str,
    prompt_template: str = "Work on: {goal}",
    checkpoint_before: bool = False,
    checkpoint_after: bool = False,
    input_from: list[str] | None = None,
    max_iterations: int = 1,
) -> dict:
    return {
        "stage_id": stage_id,
        "title": title,
        "prompt_template": prompt_template,
        "checkpoint_before": checkpoint_before,
        "checkpoint_after": checkpoint_after,
        "input_from": input_from or [],
        "iteration_policy": {"max_iterations": max_iterations},
    }


# ---------------------------------------------------------------------------
# 1. create_project_builds_stages
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_project_builds_stages():
    from src.executive.project_service import create_project
    from src.executive.project_storage import get_project

    project = await create_project(
        title="Test Project",
        goal="Test the creation logic",
        stages_raw=[
            _stage_raw("research", "Research"),
            _stage_raw("draft", "Draft"),
        ],
    )

    assert project.project_id
    assert len(project.stages) == 2
    assert project.stages[0].stage_id == "research"
    assert project.stages[1].stage_id == "draft"

    # Persisted to SQLite
    loaded = get_project(project.project_id)
    assert loaded is not None
    assert loaded.title == "Test Project"
    assert len(loaded.stages) == 2


# ---------------------------------------------------------------------------
# 2. advance_project_starts_stage
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_advance_project_starts_stage():
    from src.executive.project_service import advance_project, create_project
    from src.executive.project_storage import get_project

    project = await create_project(
        title="Advance Test",
        goal="Execute stages",
        stages_raw=[_stage_raw("s1", "Stage 1")],
    )

    # Patch run_in_executor so no real thread is spawned
    with patch("src.executive.project_service.asyncio") as mock_asyncio:
        mock_loop = MagicMock()
        mock_asyncio.get_event_loop.return_value = mock_loop
        mock_loop.run_in_executor = MagicMock()

        result = await advance_project(project.project_id)

    assert result.status == "running"
    assert result.stage_id == "s1"
    assert result.iteration == 1

    # Stage marked running in DB
    loaded = get_project(project.project_id)
    assert loaded.stages[0].status.value == "running"


# ---------------------------------------------------------------------------
# 3. checkpoint_before_blocks_advance
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_checkpoint_before_blocks_advance():
    from src.executive.project_service import advance_project, create_project
    from src.executive.project_storage import get_project

    project = await create_project(
        title="Checkpoint Test",
        goal="Test checkpoint blocking",
        stages_raw=[_stage_raw("s1", "Needs Approval", checkpoint_before=True)],
    )

    # Project should start in WAITING_APPROVAL due to checkpoint_before
    assert project.status.value == "waiting_approval"
    assert len(project.checkpoints) == 1
    assert project.checkpoints[0].status == "pending"

    # advance_project should return waiting_approval without running the stage
    result = await advance_project(project.project_id)
    assert result.status == "waiting_approval"
    assert result.checkpoint_id is not None

    # Stage should still be PENDING
    loaded = get_project(project.project_id)
    assert loaded.stages[0].status.value == "pending"


# ---------------------------------------------------------------------------
# 4. approve_checkpoint_unblocks_advance
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_approve_checkpoint_unblocks_advance():
    from src.executive.project_service import approve_checkpoint, create_project
    from src.executive.project_storage import get_project

    project = await create_project(
        title="Approve Test",
        goal="Test checkpoint approval",
        stages_raw=[_stage_raw("s1", "Gated Stage", checkpoint_before=True)],
    )

    cp_id = project.checkpoints[0].checkpoint_id

    with patch("src.executive.project_service.asyncio") as mock_asyncio:
        mock_loop = MagicMock()
        mock_asyncio.get_event_loop.return_value = mock_loop
        mock_loop.run_in_executor = MagicMock()

        result = await approve_checkpoint(project.project_id, cp_id, notes="Looks good")

    assert result["status"] == "approved"

    loaded = get_project(project.project_id)
    cp = next(c for c in loaded.checkpoints if c.checkpoint_id == cp_id)
    assert cp.status == "approved"
    assert cp.decision_notes == "Looks good"


# ---------------------------------------------------------------------------
# 5. iterate_stage_increments_count
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_iterate_stage_increments_count():
    from src.executive.project_service import create_project, iterate_stage
    from src.executive.project_storage import get_project, save_project
    from src.executive.project_models import StageStatus

    project = await create_project(
        title="Iterate Test",
        goal="Test iteration",
        stages_raw=[_stage_raw("s1", "Editable Stage", max_iterations=3)],
    )

    # Manually mark stage as COMPLETED so iterate_stage accepts it
    project.stages[0].status = StageStatus.COMPLETED
    project.stages[0].iteration_count = 1
    save_project(project)

    with patch("src.executive.project_service.asyncio") as mock_asyncio:
        mock_loop = MagicMock()
        mock_asyncio.get_event_loop.return_value = mock_loop
        mock_loop.run_in_executor = MagicMock()

        result = await iterate_stage(project.project_id, "s1", instruction="Improve clarity")

    assert result["status"] == "running"
    assert result["iteration"] == 2


# ---------------------------------------------------------------------------
# 6. iteration_policy_max_respected
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_iteration_policy_max_respected():
    from src.executive.project_service import create_project, iterate_stage
    from src.executive.project_storage import save_project
    from src.executive.project_models import StageStatus

    project = await create_project(
        title="Max Iter Test",
        goal="Respect max_iterations",
        stages_raw=[_stage_raw("s1", "Limited Stage", max_iterations=2)],
    )

    project.stages[0].status = StageStatus.COMPLETED
    project.stages[0].iteration_count = 2  # Already at max
    save_project(project)

    with pytest.raises(ValueError, match="max_iterations"):
        await iterate_stage(project.project_id, "s1")


# ---------------------------------------------------------------------------
# 7. output_chaining_between_stages
# ---------------------------------------------------------------------------


def test_output_chaining_between_stages():
    """render_stage_prompt injects prior stage output into prompt."""
    from src.executive.template import render_stage_prompt
    from src.executive.project_models import ExecutiveProject, WorkflowStage, TerminationCondition
    from datetime import datetime

    research_stage = WorkflowStage(
        stage_id="research",
        title="Research",
        prompt_template="Research: {goal}",
    )
    research_stage.current_output = "Research findings here."

    edit_stage = WorkflowStage(
        stage_id="edit",
        title="Edit",
        prompt_template="Edit iteration {iteration}. Prior output:\n{previous_output}",
        input_from=["research"],
    )

    now = datetime.now(UTC)
    project = ExecutiveProject(
        project_id="proj-1",
        title="Test",
        goal="Write a report",
        stages=[research_stage, edit_stage],
        current_stage_index=1,
        created_at=now,
        updated_at=now,
    )

    previous_outputs = {"research": "Research findings here."}
    rendered = render_stage_prompt(edit_stage, project, previous_outputs)

    assert "Edit iteration 1" in rendered
    assert "Research findings here." in rendered


# ---------------------------------------------------------------------------
# 8. time_bounded_termination
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_time_bounded_termination():
    from src.executive.project_service import _check_termination
    from src.executive.project_models import ExecutiveProject, WorkflowStage, TerminationCondition
    from datetime import datetime, timedelta

    past_start = datetime.now(UTC) - timedelta(minutes=120)
    now = datetime.now(UTC)

    stage = WorkflowStage(stage_id="s1", title="S1", prompt_template="Do: {goal}")
    project = ExecutiveProject(
        project_id="p1",
        title="Timed Project",
        goal="Test time termination",
        stages=[stage],
        termination=TerminationCondition(max_duration_minutes=60),
        started_at=past_start,
        created_at=past_start,
        updated_at=now,
    )

    should_terminate = await _check_termination(project)
    assert should_terminate is True


# ---------------------------------------------------------------------------
# 9. goal_check_llm_assessment
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_goal_check_llm_assessment():
    from src.executive.project_service import assess_goal_completion
    from src.executive.project_models import ExecutiveProject, WorkflowStage, TerminationCondition, StageOutput
    from datetime import datetime

    now = datetime.now(UTC)
    stage = WorkflowStage(stage_id="s1", title="Research", prompt_template="Research: {goal}")
    stage.outputs = [StageOutput(iteration=1, output="Comprehensive research report.", created_at=now)]
    stage.current_output = "Comprehensive research report."

    project = ExecutiveProject(
        project_id="p1",
        title="Goal Check Project",
        goal="Write a comprehensive research report",
        stages=[stage],
        termination=TerminationCondition(
            goal_reached_prompt="Has a comprehensive research report been produced? Answer yes or no."
        ),
        created_at=now,
        updated_at=now,
    )

    mock_response = MagicMock()
    mock_response.content = "yes\nThe report covers all required topics comprehensively."

    with patch("src.models.factory.create_chat_model") as mock_factory:
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        mock_factory.return_value = mock_model

        reached, reasoning = await assess_goal_completion(project)

    assert reached is True
    assert "yes" in reasoning.lower()


# ---------------------------------------------------------------------------
# 10. project_storage_roundtrip
# ---------------------------------------------------------------------------


def test_project_storage_roundtrip():
    """save_project / get_project / list_projects / delete_project."""
    import asyncio
    from src.executive.project_service import create_project
    from src.executive.project_storage import delete_project, get_project, list_projects

    project = asyncio.run(
        create_project(
            title="Storage Test",
            goal="Test CRUD",
            stages_raw=[_stage_raw("s1", "S1")],
        )
    )
    pid = project.project_id

    # get
    loaded = get_project(pid)
    assert loaded is not None
    assert loaded.title == "Storage Test"

    # list
    all_projects = list_projects()
    ids = [p.project_id for p in all_projects]
    assert pid in ids

    # delete
    delete_project(pid)
    assert get_project(pid) is None
