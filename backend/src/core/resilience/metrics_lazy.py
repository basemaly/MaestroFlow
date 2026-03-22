"""
Lazy-loaded metrics to avoid circular import dependencies.

This module provides functions to record metrics without importing
the metrics module at module load time.
"""

from typing import Optional, Callable

_metrics_module: Optional[object] = None
_structured_logger: Optional[object] = None


def _ensure_metrics_module() -> object:
    """Lazily import and cache metrics module."""
    global _metrics_module
    if _metrics_module is None:
        from src.observability import metrics as m

        _metrics_module = m
    return _metrics_module


def _ensure_structured_logger() -> object:
    """Lazily import and cache structured logger."""
    global _structured_logger
    if _structured_logger is None:
        from src.observability.structured_logging import get_structured_logger

        _structured_logger = get_structured_logger()
    return _structured_logger


def record_circuit_breaker_state_change(
    service: str,
    from_state: str,
    to_state: str,
    metrics: dict | None = None,
) -> None:
    """Record circuit breaker state change."""
    try:
        m = _ensure_metrics_module()
        if hasattr(m, "record_circuit_breaker_state_change"):
            m.record_circuit_breaker_state_change(service, from_state, to_state)
    except Exception:
        pass


def record_circuit_breaker_failure(
    service: str,
    error: str | None = None,
    details: dict | None = None,
) -> None:
    """Record circuit breaker failure."""
    try:
        m = _ensure_metrics_module()
        if hasattr(m, "record_circuit_breaker_failure"):
            m.record_circuit_breaker_failure(service)
    except Exception:
        pass


def record_circuit_breaker_success(service: str, response_time: float | None = None) -> None:
    """Record circuit breaker success."""
    try:
        m = _ensure_metrics_module()
        if hasattr(m, "record_circuit_breaker_success"):
            m.record_circuit_breaker_success(service)
    except Exception:
        pass


def record_circuit_breaker_open_duration(service: str, duration: float) -> None:
    """Record circuit breaker open duration."""
    try:
        m = _ensure_metrics_module()
        if hasattr(m, "record_circuit_breaker_open_duration"):
            m.record_circuit_breaker_open_duration(service, duration)
    except Exception:
        pass


def record_circuit_breaker_half_open_attempt(service: str) -> None:
    """Record circuit breaker half-open attempt."""
    try:
        m = _ensure_metrics_module()
        if hasattr(m, "record_circuit_breaker_half_open_attempt"):
            m.record_circuit_breaker_half_open_attempt(service)
    except Exception:
        pass


def record_http_client_request(
    service: str,
    status: str,
    duration_seconds: float,
    **_: object,
) -> None:
    """Record HTTP client request."""
    try:
        m = _ensure_metrics_module()
        if hasattr(m, "record_http_client_request"):
            m.record_http_client_request(service, status, duration_seconds)
    except Exception:
        pass


def record_http_client_retry(
    service: str,
    attempt: int | None = None,
    error: str | None = None,
) -> None:
    """Record HTTP client retry."""
    try:
        m = _ensure_metrics_module()
        if hasattr(m, "record_http_client_retry"):
            m.record_http_client_retry(service)
    except Exception:
        pass


def get_structured_logger() -> object:
    """Get structured logger."""
    return _ensure_structured_logger()
