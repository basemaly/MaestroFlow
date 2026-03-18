import logging
from typing import Any

from langchain.tools import BaseTool

from src.config import get_app_config, is_langfuse_enabled
from src.reflection import resolve_variable
from src.tools.builtins import (
    ask_clarification_tool,
    calibre_library_search,
    present_file_tool,
    task_tool,
    view_image_tool,
)

logger = logging.getLogger(__name__)


def _wrap_tool_with_tracing(t: BaseTool) -> BaseTool:
    """Monkey-patch invoke/ainvoke to add a Langfuse tool span around each call.

    Pydantic-backed tool instances reject normal attribute assignment for methods
    like ``invoke`` and ``ainvoke``. Use ``object.__setattr__`` so cached MCP and
    StructuredTool instances can still be wrapped without tripping model field
    validation, and mark wrapped tools to avoid stacking nested wrappers.
    """
    if getattr(t, "_langfuse_traced", False):
        return t

    original_invoke = t.invoke
    original_ainvoke = t.ainvoke
    tool_name = t.name

    def traced_invoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
        from src.observability import observe_span
        with observe_span(f"tool.{tool_name}", as_type="tool", input=input):
            return original_invoke(input, config, **kwargs)

    async def traced_ainvoke(input: Any, config: Any = None, **kwargs: Any) -> Any:
        from src.observability import observe_span
        with observe_span(f"tool.{tool_name}", as_type="tool", input=input):
            return await original_ainvoke(input, config, **kwargs)

    object.__setattr__(t, "invoke", traced_invoke)
    object.__setattr__(t, "ainvoke", traced_ainvoke)
    object.__setattr__(t, "_langfuse_traced", True)
    return t

BUILTIN_TOOLS = [
    present_file_tool,
    ask_clarification_tool,
    calibre_library_search,
]

SUBAGENT_TOOLS = [
    task_tool,
    # task_status_tool is no longer exposed to LLM (backend handles polling internally)
]


def _include_tool_group(tool_group: str, groups: list[str] | None, allowed_extra: set[str]) -> bool:
    """Determine whether a tool group should be loaded.

    Tools in groups starting with "opt:" are excluded by default and must be
    explicitly requested via allowed_extra. Standard groups are included unless
    a groups allowlist is provided.
    """
    if tool_group.startswith("opt:"):
        return tool_group in allowed_extra
    if groups is None:
        return True
    return tool_group in groups


def get_available_tools(
    groups: list[str] | None = None,
    include_mcp: bool = True,
    model_name: str | None = None,
    subagent_enabled: bool = False,
    extra_groups: list[str] | None = None,
) -> list[BaseTool]:
    """Get all available tools from config.

    Note: MCP tools should be initialized at application startup using
    `initialize_mcp_tools()` from src.mcp module.

    Args:
        groups: Optional list of tool groups to filter by. None means all non-optional groups.
        include_mcp: Whether to include tools from MCP servers (default: True).
        model_name: Optional model name to determine if vision tools should be included.
        subagent_enabled: Whether to include subagent tools (task, task_status).
        extra_groups: Optional list of opt-in group names (prefixed "opt:") to include.
            Tools in groups starting with "opt:" are excluded by default and must be
            explicitly requested via this parameter.

    Returns:
        List of available tools.
    """
    config = get_app_config()
    allowed_extra: set[str] = set(extra_groups or [])

    # Load from config.tools (ToolConfig list)
    loaded_tools: list[BaseTool] = []
    for tool in config.tools:
        if _include_tool_group(tool.group, groups, allowed_extra):
            try:
                loaded_tools.append(resolve_variable(tool.use, BaseTool))
            except Exception as e:
                logger.warning("Failed to load tool '%s' from config.tools: %s", tool.name, e)

    # Also load from config.tool_groups entries that have a 'use' field (backward compat)
    for tg in config.tool_groups:
        use_path: str | None = getattr(tg, "use", None)
        tg_group: str = getattr(tg, "group", tg.name)
        if not use_path:
            continue
        if not _include_tool_group(tg_group, groups, allowed_extra):
            continue
        try:
            loaded_tools.append(resolve_variable(use_path, BaseTool))
        except Exception as e:
            logger.warning("Failed to load tool '%s' from tool_groups: %s", tg.name, e)

    # Get cached MCP tools if enabled
    # NOTE: We use ExtensionsConfig.from_file() instead of config.extensions
    # to always read the latest configuration from disk. This ensures that changes
    # made through the Gateway API (which runs in a separate process) are immediately
    # reflected when loading MCP tools.
    mcp_tools = []
    if include_mcp:
        try:
            from src.config.extensions_config import ExtensionsConfig
            from src.mcp.cache import get_cached_mcp_tools

            extensions_config = ExtensionsConfig.from_file()
            if extensions_config.get_enabled_mcp_servers():
                mcp_tools = get_cached_mcp_tools()
                if mcp_tools:
                    logger.info(f"Using {len(mcp_tools)} cached MCP tool(s)")
        except ImportError:
            logger.warning("MCP module not available. Install 'langchain-mcp-adapters' package to enable MCP tools.")
        except Exception as e:
            logger.error(f"Failed to get cached MCP tools: {e}")

    # Conditionally add tools based on config
    builtin_tools = BUILTIN_TOOLS.copy()

    # Add subagent tools only if enabled via runtime parameter
    if subagent_enabled:
        builtin_tools.extend(SUBAGENT_TOOLS)
        logger.info("Including subagent tools (task)")

    # If no model_name specified, use the first model (default)
    if model_name is None and config.models:
        model_name = config.models[0].name

    # Add view_image_tool only if the model supports vision
    model_config = config.get_model_config(model_name) if model_name else None
    if model_config is not None and model_config.supports_vision:
        builtin_tools.append(view_image_tool)
        logger.info(f"Including view_image_tool for model '{model_name}' (supports_vision=True)")

    all_tools = loaded_tools + builtin_tools + mcp_tools

    if is_langfuse_enabled():
        all_tools = [_wrap_tool_with_tracing(t) for t in all_tools]

    return all_tools
