"""
Observability configuration for MaestroFlow.

Configurable via environment variables:
- METRICS_ENABLED: Enable/disable metrics collection (default: true)
- PROMETHEUS_PORT: Port for Prometheus scraping (default: 9090)
- HEALTH_CHECK_INTERVAL_SECONDS: Interval for health checks (default: 60)
- MEMORY_THRESHOLD_MB: Memory usage threshold in MB (default: 1024)
- DB_POOL_MAX_SIZE: Maximum database pool size (default: 10)
- DB_POOL_IDLE_TIMEOUT_SECONDS: Idle connection timeout (default: 300)
- LANGFUSE_ENABLED: Enable/disable Langfuse distributed tracing (default: true)
- LANGFUSE_PUBLIC_KEY: Langfuse public API key
- LANGFUSE_SECRET_KEY: Langfuse secret API key
- LANGFUSE_HOST: Langfuse API host (default: https://cloud.langfuse.io)
- LANGFUSE_TIMEOUT_SECONDS: Timeout for trace batching (default: 30)

Health thresholds for composite scoring:
- DB_HEALTH_THRESHOLD_SLOW_QUERY_MS: Threshold for slow queries (default: 1000ms)
- QUEUE_HEALTH_THRESHOLD_DEPTH_PERCENT: Queue depth alert threshold (default: 80%)
- CACHE_HEALTH_THRESHOLD_HIT_RATIO_PERCENT: Cache hit ratio warning (default: 20%)
- MEMORY_HEALTH_THRESHOLD_GROWTH_RATE_MB_MIN: Memory growth rate alert (default: 5 MB/min)
- WEBSOCKET_HEALTH_THRESHOLD_ERROR_RATE_PERCENT: WebSocket error rate threshold (default: 5%)
"""

import os
from typing import Optional


class ObservabilityConfig:
    """Configuration for observability features."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        # Metrics collection
        self.METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
        self.PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))
        self.HEALTH_CHECK_INTERVAL_SECONDS = int(
            os.getenv("HEALTH_CHECK_INTERVAL_SECONDS", "60")
        )

        # Memory monitoring
        self.MEMORY_THRESHOLD_MB = int(os.getenv("MEMORY_THRESHOLD_MB", "1024"))

        # Connection pool configuration
        self.DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
        self.DB_POOL_IDLE_TIMEOUT_SECONDS = int(
            os.getenv("DB_POOL_IDLE_TIMEOUT_SECONDS", "300")
        )

        # Langfuse distributed tracing configuration
        self.LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
        self.LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.io")
        self.LANGFUSE_TIMEOUT_SECONDS = int(os.getenv("LANGFUSE_TIMEOUT_SECONDS", "30"))
        self.LANGFUSE_SAMPLE_RATE = float(
            os.getenv("LANGFUSE_SAMPLE_RATE", "1.0")
        )  # 1.0 = 100% sampling

        # Health scoring thresholds
        self.DB_HEALTH_THRESHOLD_SLOW_QUERY_MS = int(
            os.getenv("DB_HEALTH_THRESHOLD_SLOW_QUERY_MS", "1000")
        )
        self.QUEUE_HEALTH_THRESHOLD_DEPTH_PERCENT = int(
            os.getenv("QUEUE_HEALTH_THRESHOLD_DEPTH_PERCENT", "80")
        )
        self.CACHE_HEALTH_THRESHOLD_HIT_RATIO_PERCENT = int(
            os.getenv("CACHE_HEALTH_THRESHOLD_HIT_RATIO_PERCENT", "20")
        )
        self.MEMORY_HEALTH_THRESHOLD_GROWTH_RATE_MB_MIN = float(
            os.getenv("MEMORY_HEALTH_THRESHOLD_GROWTH_RATE_MB_MIN", "5.0")
        )
        self.WEBSOCKET_HEALTH_THRESHOLD_ERROR_RATE_PERCENT = float(
            os.getenv("WEBSOCKET_HEALTH_THRESHOLD_ERROR_RATE_PERCENT", "5.0")
        )

    def __repr__(self) -> str:
        """String representation of configuration."""
        return (
            f"ObservabilityConfig("
            f"metrics_enabled={self.METRICS_ENABLED}, "
            f"prometheus_port={self.PROMETHEUS_PORT}, "
            f"health_check_interval={self.HEALTH_CHECK_INTERVAL_SECONDS}s, "
            f"memory_threshold={self.MEMORY_THRESHOLD_MB}MB, "
            f"db_pool_max_size={self.DB_POOL_MAX_SIZE}, "
            f"db_pool_idle_timeout={self.DB_POOL_IDLE_TIMEOUT_SECONDS}s, "
            f"langfuse_enabled={self.LANGFUSE_ENABLED}, "
            f"langfuse_host={self.LANGFUSE_HOST}, "
            f"langfuse_sample_rate={self.LANGFUSE_SAMPLE_RATE}, "
            f"db_health_slow_query_ms={self.DB_HEALTH_THRESHOLD_SLOW_QUERY_MS}, "
            f"queue_health_depth_percent={self.QUEUE_HEALTH_THRESHOLD_DEPTH_PERCENT}, "
            f"cache_health_hit_ratio_percent={self.CACHE_HEALTH_THRESHOLD_HIT_RATIO_PERCENT}, "
            f"memory_health_growth_rate_mb_min={self.MEMORY_HEALTH_THRESHOLD_GROWTH_RATE_MB_MIN}, "
            f"websocket_health_error_rate_percent={self.WEBSOCKET_HEALTH_THRESHOLD_ERROR_RATE_PERCENT}"
            f")"
        )


# Global config instance
_config: Optional[ObservabilityConfig] = None


def get_config() -> ObservabilityConfig:
    """Get or create the global observability configuration."""
    global _config
    if _config is None:
        _config = ObservabilityConfig()
    return _config


def load_config() -> ObservabilityConfig:
    """Load configuration. Called at application startup."""
    global _config
    _config = ObservabilityConfig()
    return _config
