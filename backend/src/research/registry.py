"""External Research Tool Registry.

Maintains a catalogue of specialist research services (GPT Researcher, Jina
DeepResearch, Perplexica, STORM) and exposes helpers for selecting the best
tool for a given task description.

Each tool is registered as a `ResearchTool` dataclass with:
- availability detection via env-var or config check
- a prompt-injection helper that adds a tool-use hint to a subagent prompt
- a capability tag set for heuristic matching

No external calls are made at import time; availability is lazy-evaluated.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ResearchCapability(str, Enum):
    WEB_SEARCH = "web_search"           # General web retrieval
    DEEP_RESEARCH = "deep_research"     # Multi-step iterative research
    ACADEMIC = "academic"               # Academic paper search
    SYNTHESIS = "synthesis"             # Cross-source synthesis / report writing
    LOCAL_LLM = "local_llm"            # Can run fully offline via local model


@dataclass
class ResearchTool:
    """A registered specialist research tool."""

    name: str
    description: str
    capabilities: frozenset[ResearchCapability] = field(default_factory=frozenset)
    env_var: str | None = None          # Environment variable that enables the tool
    config_key: str | None = None       # config.yaml key path (dot-separated)
    prompt_hint: str = ""               # One-liner injected into subagent prompts
    priority: int = 50                  # Higher = preferred when capabilities match (0-100)

    def is_available(self) -> bool:
        """Return True when the tool's required env-var (if any) is set and non-empty."""
        if self.env_var is None:
            return True  # Built-in / always-available tool
        return bool(os.environ.get(self.env_var, "").strip())

    def inject_prompt_hint(self, base_prompt: str) -> str:
        """Append the tool hint to a subagent prompt when this tool is available."""
        if not self.prompt_hint or not self.is_available():
            return base_prompt
        return f"{base_prompt}\n\n[Research hint: {self.prompt_hint}]"


# ---------------------------------------------------------------------------
# Registry definition
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, ResearchTool] = {
    "gpt-researcher": ResearchTool(
        name="gpt-researcher",
        description="GPT Researcher — autonomous deep-research agent producing long-form reports.",
        capabilities=frozenset({
            ResearchCapability.WEB_SEARCH,
            ResearchCapability.DEEP_RESEARCH,
            ResearchCapability.SYNTHESIS,
        }),
        env_var="GPT_RESEARCHER_URL",
        prompt_hint=(
            "A GPT Researcher service is available at $GPT_RESEARCHER_URL. "
            "For comprehensive research tasks, use `curl -X POST $GPT_RESEARCHER_URL/report` "
            "with JSON body `{\"query\": \"<your query>\"}` to generate a detailed report."
        ),
        priority=90,
    ),
    "jina-deepresearch": ResearchTool(
        name="jina-deepresearch",
        description="Jina DeepResearch — iterative web research with source ranking and synthesis.",
        capabilities=frozenset({
            ResearchCapability.WEB_SEARCH,
            ResearchCapability.DEEP_RESEARCH,
            ResearchCapability.SYNTHESIS,
        }),
        env_var="JINA_API_KEY",
        prompt_hint=(
            "Jina DeepResearch is available (JINA_API_KEY is set). "
            "Use `curl -H 'Authorization: Bearer $JINA_API_KEY' "
            "'https://deepsearch.jina.ai/v1/chat/completions' -d '{\"messages\":[{\"role\":\"user\",\"content\":\"<query>\"}]}'` "
            "for deep iterative research with source citations."
        ),
        priority=80,
    ),
    "perplexica": ResearchTool(
        name="perplexica",
        description="Perplexica — open-source Perplexity alternative for local/private web research.",
        capabilities=frozenset({
            ResearchCapability.WEB_SEARCH,
            ResearchCapability.DEEP_RESEARCH,
            ResearchCapability.LOCAL_LLM,
        }),
        env_var="PERPLEXICA_URL",
        prompt_hint=(
            "A Perplexica instance is available at $PERPLEXICA_URL. "
            "POST to `$PERPLEXICA_URL/api/chat` with `{\"query\": \"<your question>\", \"focusMode\": \"webSearch\"}` "
            "for privacy-preserving web research."
        ),
        priority=70,
    ),
    "storm": ResearchTool(
        name="storm",
        description="STORM (Stanford) — Wikipedia-style article generation from multi-perspective research.",
        capabilities=frozenset({
            ResearchCapability.WEB_SEARCH,
            ResearchCapability.ACADEMIC,
            ResearchCapability.SYNTHESIS,
        }),
        env_var="STORM_URL",
        prompt_hint=(
            "A STORM research service is available at $STORM_URL. "
            "POST to `$STORM_URL/generate` with `{\"topic\": \"<topic>\"}` "
            "to generate a structured, multi-perspective research article."
        ),
        priority=60,
    ),
    "tavily": ResearchTool(
        name="tavily",
        description="Tavily Search — fast AI-native web search (already a built-in tool).",
        capabilities=frozenset({
            ResearchCapability.WEB_SEARCH,
        }),
        env_var="TAVILY_API_KEY",
        prompt_hint="",  # Already in the agent's built-in toolset; no extra hint needed
        priority=40,
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_research_tool(name: str) -> ResearchTool | None:
    """Return a registered research tool by name, or None if unknown."""
    return _REGISTRY.get(name)


def list_research_tools(available_only: bool = False) -> list[ResearchTool]:
    """Return all registered research tools, optionally filtered to available ones."""
    tools = list(_REGISTRY.values())
    if available_only:
        tools = [t for t in tools if t.is_available()]
    return sorted(tools, key=lambda t: -t.priority)


def best_tool_for(
    capabilities: set[ResearchCapability],
    available_only: bool = True,
) -> ResearchTool | None:
    """Return the highest-priority tool that satisfies all requested capabilities.

    Args:
        capabilities: Required capability set (all must be present).
        available_only: Skip tools whose env-var is not set (default: True).

    Returns:
        The best matching ResearchTool, or None if no match.
    """
    candidates = [
        t for t in list_research_tools(available_only=available_only)
        if capabilities.issubset(t.capabilities)
    ]
    return candidates[0] if candidates else None


def inject_research_hints(prompt: str, task_description: str = "") -> str:
    """Append research tool hints to a subagent prompt when deep-research tools are available.

    Selects the single best deep-research tool (if any is configured) and appends
    its prompt hint. Does not inject if no tools are available or hint is empty.

    Args:
        prompt: The base subagent prompt.
        task_description: Optional task description used to check relevance heuristic.

    Returns:
        Prompt with optional research hint appended.
    """
    # Only inject for text-heavy research-style tasks
    research_keywords = frozenset(("research", "analyze", "investigate", "summarize", "report", "find information"))
    combined = (prompt + " " + task_description).lower()
    if not any(kw in combined for kw in research_keywords):
        return prompt

    tool = best_tool_for({ResearchCapability.DEEP_RESEARCH}, available_only=True)
    if tool is None:
        return prompt

    logger.debug("Injecting research hint from '%s' into subagent prompt", tool.name)
    return tool.inject_prompt_hint(prompt)
