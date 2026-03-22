"""
Cache operation monitoring and performance tracking for MaestroFlow.

Provides:
- Cache hit/miss tracking
- Cache hit ratio calculation
- Cache eviction monitoring
- Decorator-based transparent instrumentation
- Support for multiple cache types (in-memory, Redis, memcached)
- Cache coherence monitoring (optional)
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """Metrics for a single cache instance."""

    name: str
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_ratio(self) -> float:
        """Calculate cache hit ratio (0-1)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    @property
    def hit_ratio_percent(self) -> float:
        """Calculate cache hit ratio as percentage."""
        return self.hit_ratio * 100

    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1

    def record_eviction(self, reason: str = "unknown") -> None:
        """Record a cache eviction."""
        self.evictions += 1


class CacheTracker:
    """
    Centralized cache operation tracker.

    Tracks multiple caches, calculates hit ratios, and detects thrashing.
    """

    def __init__(self, eviction_rate_threshold_per_minute: float = 100.0):
        """
        Initialize cache tracker.

        Args:
            eviction_rate_threshold_per_minute: Alert if evictions exceed this per minute
        """
        self.caches: dict[str, CacheMetrics] = {}
        self.eviction_threshold = eviction_rate_threshold_per_minute
        self._last_eviction_check = time.time()

    def track_cache(self, cache_name: str) -> None:
        """Register a cache for tracking."""
        if cache_name not in self.caches:
            self.caches[cache_name] = CacheMetrics(name=cache_name)

    def record_hit(self, cache_name: str) -> None:
        """Record a cache hit."""
        if cache_name not in self.caches:
            self.track_cache(cache_name)
        self.caches[cache_name].record_hit()

    def record_miss(self, cache_name: str) -> None:
        """Record a cache miss."""
        if cache_name not in self.caches:
            self.track_cache(cache_name)
        self.caches[cache_name].record_miss()

    def record_eviction(self, cache_name: str, reason: str = "unknown") -> None:
        """Record a cache eviction and check for thrashing."""
        if cache_name not in self.caches:
            self.track_cache(cache_name)

        metrics = self.caches[cache_name]
        metrics.record_eviction(reason)

        # Check for thrashing every 60 seconds
        now = time.time()
        if now - self._last_eviction_check >= 60:
            self._check_eviction_rate(cache_name)
            self._last_eviction_check = now

    def _check_eviction_rate(self, cache_name: str) -> None:
        """Check if eviction rate indicates cache thrashing."""
        metrics = self.caches[cache_name]
        # This is simplified; in production, track evictions per time window
        if metrics.evictions > self.eviction_threshold:
            logger.warning(
                f"Cache '{cache_name}' high eviction count ({metrics.evictions}); "
                f"possible thrashing detected"
            )

    def get_metrics(self, cache_name: str) -> Optional[CacheMetrics]:
        """Get metrics for a specific cache."""
        return self.caches.get(cache_name)

    def get_all_metrics(self) -> dict[str, CacheMetrics]:
        """Get metrics for all registered caches."""
        return dict(self.caches)

    def get_health_status(self) -> tuple[str, dict]:
        """
        Get overall cache health status.

        Returns:
            Tuple of (status, details) where status is 'healthy', 'degraded', or 'unhealthy'
        """
        if not self.caches:
            return "healthy", {}

        details = {}
        worst_status = "healthy"

        for cache_name, metrics in self.caches.items():
            cache_detail = {
                "hits": metrics.hits,
                "misses": metrics.misses,
                "hit_ratio_percent": round(metrics.hit_ratio_percent, 1),
                "evictions": metrics.evictions,
            }
            details[cache_name] = cache_detail

            # Determine cache status
            if metrics.hit_ratio_percent < 5:
                cache_status = "unhealthy"
            elif metrics.hit_ratio_percent < 20:
                cache_status = "degraded"
            else:
                cache_status = "healthy"

            # Track worst status across all caches
            if cache_status == "unhealthy":
                worst_status = "unhealthy"
            elif cache_status == "degraded" and worst_status != "unhealthy":
                worst_status = "degraded"

        return worst_status, details

    def clear_all(self) -> None:
        """Clear all cache metrics (useful for testing)."""
        self.caches.clear()


# Global cache tracker instance
_cache_tracker: Optional[CacheTracker] = None


def initialize_cache_tracker() -> CacheTracker:
    """
    Initialize global cache tracker.

    Returns:
        Initialized CacheTracker instance
    """
    global _cache_tracker
    _cache_tracker = CacheTracker()
    logger.info("Cache tracker initialized")
    return _cache_tracker


def get_cache_tracker() -> Optional[CacheTracker]:
    """Get the global cache tracker instance."""
    return _cache_tracker


def track_cache_operation(
    cache_name: str = "default",
    operation_type: str = "get",
    metrics_registry=None,
):
    """
    Decorator to transparently track cache operations.

    Args:
        cache_name: Name of the cache being tracked
        operation_type: Type of operation ('get', 'put', 'delete', etc.)
        metrics_registry: Optional MetricsRegistry for Prometheus integration

    Example:
        @track_cache_operation('user_cache', 'get')
        def get_user(user_id):
            # actual cache lookup
            return cache.get(f'user:{user_id}')
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            tracker = get_cache_tracker()
            if tracker:
                tracker.track_cache(cache_name)

            result = func(*args, **kwargs)

            if tracker and result is not None:
                tracker.record_hit(cache_name)
                if metrics_registry:
                    metrics_registry.record_cache_hit(cache_name)
            elif tracker:
                tracker.record_miss(cache_name)
                if metrics_registry:
                    metrics_registry.record_cache_miss(cache_name)

            return result

        async def async_wrapper(*args, **kwargs) -> Any:
            tracker = get_cache_tracker()
            if tracker:
                tracker.track_cache(cache_name)

            result = await func(*args, **kwargs)

            if tracker and result is not None:
                tracker.record_hit(cache_name)
                if metrics_registry:
                    metrics_registry.record_cache_hit(cache_name)
            elif tracker:
                tracker.record_miss(cache_name)
                if metrics_registry:
                    metrics_registry.record_cache_miss(cache_name)

            return result

        # Choose wrapper based on function type
        if hasattr(func, "__await__"):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def record_cache_metrics(metrics_registry) -> None:
    """
    Record current cache metrics to Prometheus.

    Args:
        metrics_registry: MetricsRegistry instance
    """
    tracker = get_cache_tracker()
    if not tracker:
        return

    for cache_name, metrics in tracker.get_all_metrics().items():
        metrics_registry.cache_hits_total.labels(cache_name=cache_name)._value.set(
            metrics.hits
        )
        metrics_registry.cache_misses_total.labels(cache_name=cache_name)._value.set(
            metrics.misses
        )
        metrics_registry.cache_hit_ratio.labels(cache_name=cache_name).set(
            metrics.hit_ratio
        )
