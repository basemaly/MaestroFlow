"""Lazy exports for subagent helpers.

Avoid eager imports here because the executor stack depends on agent modules
that can create circular imports during lightweight module startup.
"""

from .config import SubagentConfig

__all__ = [
    "SubagentConfig",
    "SubagentExecutor",
    "SubagentResult",
    "get_subagent_config",
    "list_subagents",
]


def __getattr__(name: str):
    if name in {"SubagentExecutor", "SubagentResult"}:
        from .executor import SubagentExecutor, SubagentResult

        return {"SubagentExecutor": SubagentExecutor, "SubagentResult": SubagentResult}[name]
    if name in {"get_subagent_config", "list_subagents"}:
        from .registry import get_subagent_config, list_subagents

        return {"get_subagent_config": get_subagent_config, "list_subagents": list_subagents}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
