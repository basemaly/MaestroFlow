"""
Configuration for circuit breaker and resilience patterns.

Configurable via environment variables:
- CIRCUIT_FAILURE_THRESHOLD: Number of failures before opening circuit (default: 5)
- CIRCUIT_RESET_TIMEOUT: Seconds before attempting half-open state (default: 60)
- CIRCUIT_SUCCESS_THRESHOLD: Successes needed to close circuit from half-open (default: 2)
- MAX_RETRIES: Maximum retry attempts with exponential backoff (default: 3)
"""

import os
import threading
from typing import Optional

from pydantic import BaseModel, Field

_config_lock = threading.Lock()


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = Field(
        default=5,
        description="Number of consecutive failures before opening circuit",
    )
    reset_timeout: int = Field(
        default=60,
        description="Seconds to wait in OPEN state before attempting HALF_OPEN",
    )
    success_threshold: int = Field(
        default=2,
        description="Number of successes in HALF_OPEN state to close circuit",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts with exponential backoff",
    )
    timeout: float = Field(
        default=30.0,
        description="Request timeout in seconds",
    )
    retry_base_delay: float = Field(
        default=1.0,
        description="Base delay for exponential backoff in seconds",
    )
    retry_max_delay: float = Field(
        default=30.0,
        description="Maximum retry delay in seconds",
    )
    retry_jitter: bool = Field(
        default=True,
        description="Add random jitter to retry delays",
    )
    monitor_pool: bool = Field(
        default=True,
        description="Monitor connection pool health",
    )
    pool_health_check_interval: float = Field(
        default=30.0,
        description="Connection pool health check interval in seconds",
    )
    pool_max_connections: int = Field(
        default=100,
        description="Maximum connections in pool",
    )
    pool_max_keepalive: int = Field(
        default=50,
        description="Maximum keepalive connections",
    )
    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection",
    )
    metrics_window_size: int = Field(
        default=100,
        description="Number of recent requests to track for metrics",
    )


_resilience_config: Optional[CircuitBreakerConfig] = None


def get_resilience_config() -> CircuitBreakerConfig:
    """Get the singleton resilience configuration."""
    global _resilience_config
    if _resilience_config is not None:
        return _resilience_config

    with _config_lock:
        if _resilience_config is not None:
            return _resilience_config

        # Read from environment variables with defaults
        failure_threshold = int(os.environ.get("CIRCUIT_FAILURE_THRESHOLD", "5"))
        reset_timeout = int(os.environ.get("CIRCUIT_RESET_TIMEOUT", "60"))
        success_threshold = int(os.environ.get("CIRCUIT_SUCCESS_THRESHOLD", "2"))
        max_retries = int(os.environ.get("MAX_RETRIES", "3"))
        timeout = float(os.environ.get("CIRCUIT_TIMEOUT", "30.0"))
        retry_base_delay = float(os.environ.get("CIRCUIT_RETRY_BASE_DELAY", "1.0"))
        retry_max_delay = float(os.environ.get("CIRCUIT_RETRY_MAX_DELAY", "30.0"))
        retry_jitter = os.environ.get("CIRCUIT_RETRY_JITTER", "true").lower() == "true"
        monitor_pool = os.environ.get("CIRCUIT_MONITOR_POOL", "true").lower() == "true"
        pool_health_check_interval = float(os.environ.get("CIRCUIT_POOL_CHECK_INTERVAL", "30.0"))
        pool_max_connections = int(os.environ.get("CIRCUIT_POOL_MAX_CONNECTIONS", "100"))
        pool_max_keepalive = int(os.environ.get("CIRCUIT_POOL_MAX_KEEPALIVE", "50"))
        enable_metrics = os.environ.get("CIRCUIT_ENABLE_METRICS", "true").lower() == "true"
        metrics_window_size = int(os.environ.get("CIRCUIT_METRICS_WINDOW_SIZE", "100"))

        _resilience_config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            success_threshold=success_threshold,
            max_retries=max_retries,
            timeout=timeout,
            retry_base_delay=retry_base_delay,
            retry_max_delay=retry_max_delay,
            retry_jitter=retry_jitter,
            monitor_pool=monitor_pool,
            pool_health_check_interval=pool_health_check_interval,
            pool_max_connections=pool_max_connections,
            pool_max_keepalive=pool_max_keepalive,
            enable_metrics=enable_metrics,
            metrics_window_size=metrics_window_size,
        )

        return _resilience_config
