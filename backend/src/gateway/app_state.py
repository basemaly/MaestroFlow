"""Application state tracking for shutdown coordination.

This module tracks application lifecycle state including shutdown status,
allowing other components to respond appropriately during graceful shutdown.
"""

import threading
from typing import Optional

# Thread-safe application state
_state_lock = threading.Lock()
_shutdown_initiated: bool = False
_shutdown_reason: Optional[str] = None


def is_shutting_down() -> bool:
    """Check if application shutdown has been initiated.

    Returns:
        True if shutdown has been initiated, False otherwise.
    """
    with _state_lock:
        return _shutdown_initiated


def get_shutdown_reason() -> Optional[str]:
    """Get the reason for shutdown if available.

    Returns:
        Shutdown reason string, or None if shutdown not initiated.
    """
    with _state_lock:
        return _shutdown_reason


def initiate_shutdown(reason: str = "Unknown") -> None:
    """Mark shutdown as initiated.

    Args:
        reason: Description of what triggered the shutdown.
    """
    global _shutdown_initiated, _shutdown_reason
    with _state_lock:
        _shutdown_initiated = True
        _shutdown_reason = reason


def reset_shutdown_state() -> None:
    """Reset shutdown state (for testing only)."""
    global _shutdown_initiated, _shutdown_reason
    with _state_lock:
        _shutdown_initiated = False
        _shutdown_reason = None
