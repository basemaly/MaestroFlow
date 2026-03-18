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
