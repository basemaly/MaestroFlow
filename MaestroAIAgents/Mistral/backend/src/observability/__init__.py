"""
Observability module for MaestroFlow.

Provides centralized metrics collection, health checking, and distributed tracing.
"""

from .metrics import (
    MetricsRegistry,
    get_metrics,
    initialize_metrics,
)

__all__ = [
    "MetricsRegistry",
    "get_metrics",
    "initialize_metrics",
]


# Convenience functions for common operations
def record_query_time(query_type: str = "unknown"):
    """Context manager to time database queries."""
    return get_metrics().time_query(query_type)


def record_connection_wait():
    """Context manager to measure connection pool wait time."""
    return get_metrics().time_connection_wait()


def record_queue_depth(queue_name: str, depth: int) -> None:
    """Update queue depth gauge."""
    get_metrics().record_queue_depth(queue_name, depth)


def record_cache_hit(cache_name: str) -> None:
    """Record a cache hit."""
    get_metrics().record_cache_hit(cache_name)


def record_cache_miss(cache_name: str) -> None:
    """Record a cache miss."""
    get_metrics().record_cache_miss(cache_name)
