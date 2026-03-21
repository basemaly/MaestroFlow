"""Observability configuration for monitoring and metrics.

Environment Variables:
    METRICS_ENABLED: Enable/disable Prometheus metrics collection (default: True)
    METRICS_SLOW_QUERY_THRESHOLD_MS: Database query latency threshold for slow query tracking (default: 100ms)
    METRICS_HISTOGRAM_BUCKETS: Custom histogram buckets for latency metrics (default: standard)
    HEALTH_CHECK_ENABLED: Enable/disable health check endpoints (default: True)
    LANGFUSE_ENABLED: Enable/disable Langfuse distributed tracing (default: True)
    LANGFUSE_SAMPLE_RATE: Percentage of requests to trace (0-1, default: 1.0)
"""

import os
from typing import Final

# Metrics collection configuration
METRICS_ENABLED: Final[bool] = os.getenv("METRICS_ENABLED", "true").lower() in ("true", "1", "yes")

# Database query latency threshold (ms) for slow query detection
METRICS_SLOW_QUERY_THRESHOLD_MS: Final[int] = int(os.getenv("METRICS_SLOW_QUERY_THRESHOLD_MS", "100"))

# Histogram buckets for latency metrics (in seconds)
# Default buckets: 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
_HISTOGRAM_BUCKETS_ENV = os.getenv("METRICS_HISTOGRAM_BUCKETS", "")
if _HISTOGRAM_BUCKETS_ENV:
    try:
        METRICS_HISTOGRAM_BUCKETS: Final[tuple] = tuple(float(x.strip()) for x in _HISTOGRAM_BUCKETS_ENV.split(","))
    except (ValueError, AttributeError):
        METRICS_HISTOGRAM_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
else:
    METRICS_HISTOGRAM_BUCKETS = (0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# Health check configuration
HEALTH_CHECK_ENABLED: Final[bool] = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() in ("true", "1", "yes")

# Langfuse distributed tracing configuration
LANGFUSE_ENABLED: Final[bool] = os.getenv("LANGFUSE_ENABLED", "true").lower() in ("true", "1", "yes")

LANGFUSE_SAMPLE_RATE: Final[float] = float(os.getenv("LANGFUSE_SAMPLE_RATE", "1.0"))
if not 0 <= LANGFUSE_SAMPLE_RATE <= 1:
    raise ValueError(f"LANGFUSE_SAMPLE_RATE must be between 0 and 1, got {LANGFUSE_SAMPLE_RATE}")

# Connection pool configuration (for reference)
EXECUTOR_DB_MAX_POOL_SIZE: Final[int] = int(os.getenv("EXECUTOR_DB_MAX_POOL_SIZE", "20"))

EXECUTOR_DB_POOL_IDLE_TIMEOUT_SECONDS: Final[int] = int(os.getenv("EXECUTOR_DB_POOL_IDLE_TIMEOUT", "300"))

# Memory monitoring configuration
MEMORY_MONITORING_ENABLED: Final[bool] = os.getenv("MEMORY_MONITORING_ENABLED", "true").lower() in ("true", "1", "yes")

# Interval (seconds) for periodic memory monitoring
MEMORY_MONITORING_INTERVAL_SECONDS: Final[int] = int(os.getenv("MEMORY_MONITORING_INTERVAL_SECONDS", "60"))
