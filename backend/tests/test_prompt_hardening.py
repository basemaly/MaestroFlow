"""Regression tests for prompt hardening and tool instruction guardrails."""

from src.agents.lead_agent import prompt as lead_prompt
from src.agents.memory.prompt import FACT_EXTRACTION_PROMPT, MEMORY_UPDATE_PROMPT
from src.config.title_config import TitleConfig
from src.executive.tools import executive_create_project
from src.tools.builtins.calibre_ingest_tool import ingest_calibre_books_to_search_space
from src.tools.builtins.calibre_preview_tool import preview_calibre_books_for_search_space
from src.tools.builtins.clarification_tool import ask_clarification_tool
from src.tools.builtins.task_tool import task_tool


def test_lead_prompt_template_uses_dynamic_working_directory_placeholders():
    assert "{uploads_dir}" in lead_prompt.SYSTEM_PROMPT_TEMPLATE
    assert "{workspace_dir}" in lead_prompt.SYSTEM_PROMPT_TEMPLATE
    assert "{outputs_dir}" in lead_prompt.SYSTEM_PROMPT_TEMPLATE
    assert "/mnt/user-data/outputs" not in lead_prompt.SYSTEM_PROMPT_TEMPLATE


def test_rendered_lead_prompt_includes_citation_guardrails_and_dynamic_paths(monkeypatch):
    monkeypatch.setattr(lead_prompt, "_get_memory_context", lambda agent_name=None: "")
    monkeypatch.setattr(lead_prompt, "get_skills_prompt_section", lambda available_skills=None: "")
    monkeypatch.setattr(lead_prompt, "get_agent_soul", lambda agent_name=None: "")

    rendered = lead_prompt.apply_prompt_template(subagent_enabled=True, agent_name="Executive")

    assert "NEVER invent, guess, or paraphrase a URL" in rendered
    assert "Only cite URLs that were explicitly returned by tools or web results in the current run" in rendered
    assert "Invalid pattern" in rendered
    assert "/mnt/user-data/uploads" in rendered
    assert "/mnt/user-data/workspace" in rendered
    assert "/mnt/user-data/outputs" in rendered


def test_memory_update_prompt_keeps_high_visibility_constraints_and_examples():
    assert "<constraints>" in MEMORY_UPDATE_PROMPT
    assert "Do NOT record file upload events, temporary files, or other session-only artifacts." in MEMORY_UPDATE_PROMPT
    assert "Example A — durable update" in MEMORY_UPDATE_PROMPT
    assert "Example B — ignore transient/session-only info" in MEMORY_UPDATE_PROMPT


def test_fact_extraction_prompt_forbids_inference_and_shows_positive_negative_examples():
    assert "Do NOT infer facts that are not directly supported by the message" in FACT_EXTRACTION_PROMPT
    assert "Do NOT guess intent, permanence, or preferences unless the message states them clearly" in FACT_EXTRACTION_PROMPT
    assert 'Durable fact: "I prefer Python for backend work"' in FACT_EXTRACTION_PROMPT
    assert 'Skip: "I\'m tired today"' in FACT_EXTRACTION_PROMPT


def test_title_prompt_includes_strict_output_constraints_and_example():
    prompt_template = TitleConfig().prompt_template

    assert "Return exactly one line containing only the title." in prompt_template
    assert "Do not use markdown, quotes, bullets, prefixes like 'Title:', or conversational filler." in prompt_template
    assert "Example output: Setting Up the Docker Environment" in prompt_template


def test_task_tool_description_mentions_default_subagent_model_routing():
    assert "normal system routing/default behavior" in task_tool.description


def test_clarification_tool_description_mentions_omitting_options():
    assert "Omit `options` entirely" in ask_clarification_tool.description


def test_calibre_tool_descriptions_enforce_preview_before_ingest():
    assert "preview first and only call ingest after the user approves" in preview_calibre_books_for_search_space.description
    assert "call the preview tool first" in ingest_calibre_books_to_search_space.description


def test_executive_create_project_description_includes_minimal_json_example():
    description = executive_create_project.description

    assert "When to use:" in description
    assert "What it returns:" in description
    assert "Important constraints:" in description
    assert '[{"stage_id":"research","title":"Research","prompt_template":"Research {goal}","expected_output":"Bullet findings"}]' in description
