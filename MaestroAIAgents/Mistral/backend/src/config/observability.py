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
            f"langfuse_sample_rate={self.LANGFUSE_SAMPLE_RATE}"
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
