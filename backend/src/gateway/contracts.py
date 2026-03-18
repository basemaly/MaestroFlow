from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class HealthEnvelope(BaseModel):
    configured: bool
    available: bool
    healthy: bool
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)

class ErrorEnvelope(BaseModel):
    error_code: str
    message: str
    retryable: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class GatewayResponse(BaseModel, Generic[T]):
    data: T | None = None
    health: HealthEnvelope | None = None
    error: ErrorEnvelope | None = None


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
    return HealthEnvelope(
        configured=configured,
        available=available,
        healthy=resolved_healthy,
        summary=summary,
        details=details or {},
        last_error=last_error,
        metrics=metrics or {},
    ).model_dump()


def build_error_envelope(
    *,
    error_code: str,
    message: str,
    retryable: bool = True,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ErrorEnvelope(
        error_code=error_code,
        message=message,
        retryable=retryable,
        details=details or {},
    ).model_dump()
