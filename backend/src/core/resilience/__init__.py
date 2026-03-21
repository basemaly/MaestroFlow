"""
Resilience patterns for MaestroFlow backend.

This module provides circuit breaker implementations and connection pool
monitoring to handle failures gracefully and prevent cascade failures.
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitOpenError,
    CircuitState,
)

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerMetrics",
    "CircuitOpenError",
    "CircuitState",
]
