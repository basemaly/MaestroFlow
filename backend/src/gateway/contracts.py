from __future__ import annotations

from typing import Any


def build_health_envelope(
    *,
    configured: bool,
    available: bool,
    healthy: bool | None = None,
    summary: str,
    details: dict[str, Any] | None = None,
    last_error: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_healthy = healthy if healthy is not None else (available and not last_error)
    return {
        "configured": configured,
        "available": available,
        "healthy": resolved_healthy,
        "summary": summary,
        "details": details or {},
        "last_error": last_error,
        "metrics": metrics or {},
    }


def build_error_envelope(
    *,
    error_code: str,
    message: str,
    retryable: bool = True,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
        "details": details or {},
    }
