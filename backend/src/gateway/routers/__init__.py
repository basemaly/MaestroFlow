"""
Gateway routers with lazy loading to prevent cascading import failures.
"""

import importlib
from typing import Any

# List of available router modules
_AVAILABLE_ROUTERS = {
    "activepieces",
    "agents", 
    "artifacts",
    "autoresearch",
    "browser_runtime",
    "calibre",
    "channels",
    "diagnostics", 
    "doc_editing",
    "documents",
    "executive",
    "health",
    "mcp",
    "memory",
    "models",
    "openviking",
    "pinboard",
    "planning",
    "quality",
    "skills",
    "state",
    "suggestions",
    "surfsense",
    "uploads",
}

# Cache for loaded modules
_loaded_modules: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    """Lazy load router modules on first access."""
    if name in _AVAILABLE_ROUTERS:
        if name not in _loaded_modules:
            try:
                module = importlib.import_module(f".{name}", package=__name__)
                _loaded_modules[name] = module
            except ImportError as e:
                raise ImportError(f"Failed to import router '{name}': {e}") from e
        return _loaded_modules[name]
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = list(_AVAILABLE_ROUTERS)
