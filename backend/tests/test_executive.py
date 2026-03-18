import asyncio
from pathlib import Path

from src.executive.actions import confirm_approval, execute_action, preview_action
from src.executive.advisory import build_advisory
from src.executive.runtime_overrides import (
    get_default_model_override,
    get_subagent_concurrency_override,
    get_subagent_timeout_override,
)
from src.executive.status import collect_system_status
from src.executive.storage import list_approvals


def test_preview_action_describes_confirmation_requirement():
    preview = preview_action("restart_component", "litellm", {})

    assert preview.action_id == "restart_component"
    assert preview.component_id == "litellm"
    assert preview.requires_confirmation is True
    assert preview.risk_level == "high"


def test_execute_risky_action_creates_approval(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    result = asyncio.run(
        execute_action(
            "restart_component",
            "litellm",
            {},
            requested_by="tester",
        )
    )

    assert result.status == "pending_approval"
    approvals = list_approvals()
    assert len(approvals) == 1
    assert approvals[0].action_id == "restart_component"


def test_confirm_approval_executes_runtime_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    pending = asyncio.run(
        execute_action(
            "update_subagent_concurrency_policy",
            "subagents",
            {"max_concurrent_subagents": 2},
            requested_by="tester",
        )
    )
    approval_id = pending.approval_id
    assert approval_id

    confirmed = asyncio.run(confirm_approval(approval_id, actor_id="tester"))

    assert confirmed.status == "succeeded"
    assert get_subagent_concurrency_override() == 2


def test_execute_timeout_override_applies_to_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    pending = asyncio.run(
        execute_action(
            "update_subagent_timeout",
            "subagents",
            {"timeout_seconds": 1800, "agent_name": "general-purpose"},
            requested_by="tester",
        )
    )
    confirmed = asyncio.run(confirm_approval(pending.approval_id, actor_id="tester"))

    assert confirmed.status == "succeeded"
    assert get_subagent_timeout_override("general-purpose") == 1800


def test_execute_default_model_override_applies(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXECUTIVE_DB_PATH", str(tmp_path / "executive.db"))

    pending = asyncio.run(
        execute_action(
            "set_default_model",
            "lead_agent",
            {"model_name": "gemini-2-5-flash"},
            requested_by="tester",
        )
    )
    confirmed = asyncio.run(confirm_approval(pending.approval_id, actor_id="tester"))

    assert confirmed.status == "succeeded"
    assert get_default_model_override() == "gemini-2-5-flash"


def test_collect_system_status_and_advisory(monkeypatch):
    async def fake_external():
        return {
            "services": [
                {"service": "litellm", "label": "LiteLLM", "configured": True, "available": False, "required": True, "url": "http://127.0.0.1:4000", "message": "LiteLLM is unreachable: boom"},
                {"service": "langgraph", "label": "LangGraph", "configured": True, "available": True, "required": True, "url": "http://127.0.0.1:2024", "message": None},
                {"service": "langfuse", "label": "Langfuse", "configured": True, "available": True, "required": False, "url": "http://127.0.0.1:3000", "message": None},
                {"service": "surfsense", "label": "SurfSense", "configured": True, "available": True, "required": False, "url": "http://127.0.0.1:3004", "message": None},
            ],
            "degraded": True,
            "warnings": [],
        }

    monkeypatch.setattr("src.executive.status.get_external_services_status", fake_external)
    status = asyncio.run(collect_system_status())
    rules = build_advisory(status)

    litellm = next(item for item in status.components if item.component_id == "litellm")
    assert litellm.state == "unavailable"
    assert any(rule.component_id == "litellm" for rule in rules)


def test_collect_system_status_marks_disabled_component(monkeypatch):
    async def fake_external():
        return {
            "services": [
                {"service": "litellm", "label": "LiteLLM", "configured": True, "available": False, "required": True, "url": "http://127.0.0.1:4000", "message": "LiteLLM is unreachable: boom"},
                {"service": "langgraph", "label": "LangGraph", "configured": True, "available": True, "required": True, "url": "http://127.0.0.1:2024", "message": None},
                {"service": "langfuse", "label": "Langfuse", "configured": True, "available": True, "required": False, "url": "http://127.0.0.1:3000", "message": None},
                {"service": "surfsense", "label": "SurfSense", "configured": True, "available": True, "required": False, "url": "http://127.0.0.1:3004", "message": None},
            ],
            "degraded": True,
            "warnings": [],
        }

    monkeypatch.setenv("EXECUTIVE_DISABLED_COMPONENTS", "litellm")
    monkeypatch.setattr("src.executive.status.get_external_services_status", fake_external)
    status = asyncio.run(collect_system_status())
    rules = build_advisory(status)

    litellm = next(item for item in status.components if item.component_id == "litellm")
    assert litellm.state == "disabled"
    assert status.summary["disabled"] >= 1
    assert not any(rule.component_id == "litellm" for rule in rules)


def test_collect_system_status_marks_profile_disabled_component(monkeypatch):
    async def fake_external():
        return {
            "services": [
                {"service": "litellm", "label": "LiteLLM", "configured": True, "available": True, "required": True, "url": "http://127.0.0.1:4000", "message": None},
                {"service": "langgraph", "label": "LangGraph", "configured": True, "available": True, "required": True, "url": "http://127.0.0.1:2024", "message": None},
                {"service": "langfuse", "label": "Langfuse", "configured": True, "available": False, "required": False, "url": "http://127.0.0.1:3000", "message": "offline"},
                {"service": "surfsense", "label": "SurfSense", "configured": True, "available": False, "required": False, "url": "http://127.0.0.1:3004", "message": "offline"},
            ],
            "degraded": False,
            "warnings": [],
        }

    monkeypatch.setenv("MAESTROFLOW_RUNTIME_PROFILE", "core")
    monkeypatch.delenv("EXECUTIVE_DISABLED_COMPONENTS", raising=False)
    monkeypatch.setattr("src.executive.status.get_external_services_status", fake_external)
    status = asyncio.run(collect_system_status())

    by_component = {item.component_id: item for item in status.components}
    assert by_component["surfsense"].state == "disabled"
    assert by_component["langfuse"].state == "disabled"
    assert status.summary["disabled"] >= 2
