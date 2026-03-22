"""
Tests for cache operation tracking and performance monitoring.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from backend.src.observability.cache_tracking import (
    CacheMetrics,
    CacheTracker,
    initialize_cache_tracker,
    get_cache_tracker,
    track_cache_operation,
    record_cache_metrics,
)


class TestCacheMetrics:
    """Tests for CacheMetrics dataclass."""

    def test_cache_metrics_creation(self):
        """Test creating cache metrics."""
        metrics = CacheMetrics(name="user_cache", hits=50, misses=10)
        assert metrics.name == "user_cache"
        assert metrics.hits == 50
        assert metrics.misses == 10

    def test_hit_ratio_calculation(self):
        """Test cache hit ratio calculation."""
        metrics = CacheMetrics(name="test_cache", hits=80, misses=20)
        assert metrics.hit_ratio == 0.8
        assert metrics.hit_ratio_percent == 80.0

    def test_hit_ratio_zero_total(self):
        """Test hit ratio when no operations occurred."""
        metrics = CacheMetrics(name="test_cache")
        assert metrics.hit_ratio == 0.0
        assert metrics.hit_ratio_percent == 0.0

    def test_record_hit(self):
        """Test recording a cache hit."""
        metrics = CacheMetrics(name="test_cache")
        metrics.record_hit()
        assert metrics.hits == 1

    def test_record_miss(self):
        """Test recording a cache miss."""
        metrics = CacheMetrics(name="test_cache")
        metrics.record_miss()
        assert metrics.misses == 1

    def test_record_eviction(self):
        """Test recording a cache eviction."""
        metrics = CacheMetrics(name="test_cache")
        metrics.record_eviction(reason="TTL")
        assert metrics.evictions == 1


class TestCacheTracker:
    """Tests for CacheTracker class."""

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = CacheTracker(eviction_rate_threshold_per_minute=100.0)
        assert tracker.eviction_threshold == 100.0
        assert len(tracker.caches) == 0

    def test_track_cache(self):
        """Test registering a cache for tracking."""
        tracker = CacheTracker()
        tracker.track_cache("user_cache")
        assert "user_cache" in tracker.caches

    def test_record_hit(self):
        """Test recording cache hits."""
        tracker = CacheTracker()
        tracker.record_hit("user_cache")
        tracker.record_hit("user_cache")

        metrics = tracker.get_metrics("user_cache")
        assert metrics.hits == 2

    def test_record_miss(self):
        """Test recording cache misses."""
        tracker = CacheTracker()
        tracker.record_miss("user_cache")
        tracker.record_miss("user_cache")

        metrics = tracker.get_metrics("user_cache")
        assert metrics.misses == 2

    def test_record_eviction(self):
        """Test recording cache evictions."""
        tracker = CacheTracker()
        tracker.record_eviction("user_cache", reason="LRU")

        metrics = tracker.get_metrics("user_cache")
        assert metrics.evictions == 1

    def test_get_all_metrics(self):
        """Test retrieving all cache metrics."""
        tracker = CacheTracker()
        tracker.record_hit("cache1")
        tracker.record_hit("cache2")

        all_metrics = tracker.get_all_metrics()
        assert len(all_metrics) == 2
        assert "cache1" in all_metrics
        assert "cache2" in all_metrics

    def test_health_status_healthy(self):
        """Test health status when cache is healthy."""
        tracker = CacheTracker()
        tracker.record_hit(
            "cache",
        )
        for _ in range(19):
            tracker.record_hit("cache")

        status, details = tracker.get_health_status()
        assert status == "healthy"
        assert details["cache"]["hit_ratio_percent"] == 100.0

    def test_health_status_degraded_at_20_percent(self):
        """Test health status when hit ratio < 20%."""
        tracker = CacheTracker()
        tracker.record_hit("cache")
        for _ in range(4):
            tracker.record_miss("cache")

        status, details = tracker.get_health_status()
        assert status == "degraded"
        assert details["cache"]["hit_ratio_percent"] == 20.0

    def test_health_status_unhealthy_at_5_percent(self):
        """Test health status when hit ratio < 5%."""
        tracker = CacheTracker()
        tracker.record_hit("cache")
        for _ in range(19):
            tracker.record_miss("cache")

        status, details = tracker.get_health_status()
        assert status == "unhealthy"

    def test_health_status_empty_tracker(self):
        """Test health status with no caches."""
        tracker = CacheTracker()
        status, details = tracker.get_health_status()
        assert status == "healthy"
        assert len(details) == 0

    def test_clear_all(self):
        """Test clearing all metrics."""
        tracker = CacheTracker()
        tracker.record_hit("cache1")
        tracker.record_hit("cache2")
        assert len(tracker.caches) == 2

        tracker.clear_all()
        assert len(tracker.caches) == 0


class TestCacheOperationDecorator:
    """Tests for cache operation tracking decorator."""

    def test_decorator_sync_hit(self):
        """Test decorator on sync function returning a value (hit)."""
        tracker = CacheTracker()

        @track_cache_operation("test_cache", "get")
        def get_cached_value():
            return "value"

        # Initialize global tracker
        import backend.src.observability.cache_tracking as cache_module

        cache_module._cache_tracker = tracker

        result = get_cached_value()
        assert result == "value"

        metrics = tracker.get_metrics("test_cache")
        assert metrics.hits == 1
        assert metrics.misses == 0

    def test_decorator_sync_miss(self):
        """Test decorator on sync function returning None (miss)."""
        tracker = CacheTracker()

        @track_cache_operation("test_cache", "get")
        def get_cached_value():
            return None

        import backend.src.observability.cache_tracking as cache_module

        cache_module._cache_tracker = tracker

        result = get_cached_value()
        assert result is None

        metrics = tracker.get_metrics("test_cache")
        assert metrics.hits == 0
        assert metrics.misses == 1

    @pytest.mark.asyncio
    async def test_decorator_async_hit(self):
        """Test decorator on async function returning a value (hit)."""
        tracker = CacheTracker()

        @track_cache_operation("test_cache", "get")
        async def get_cached_value():
            return "async_value"

        import backend.src.observability.cache_tracking as cache_module

        cache_module._cache_tracker = tracker

        result = await get_cached_value()
        assert result == "async_value"

        metrics = tracker.get_metrics("test_cache")
        assert metrics.hits == 1


class TestCacheTrackerIntegration:
    """Integration tests for cache tracker."""

    def test_multiple_caches(self):
        """Test tracking multiple caches independently."""
        tracker = CacheTracker()

        # Populate cache1
        for _ in range(8):
            tracker.record_hit("cache1")
        for _ in range(2):
            tracker.record_miss("cache1")

        # Populate cache2
        for _ in range(1):
            tracker.record_hit("cache2")
        for _ in range(9):
            tracker.record_miss("cache2")

        metrics1 = tracker.get_metrics("cache1")
        metrics2 = tracker.get_metrics("cache2")

        assert metrics1.hit_ratio_percent == 80.0
        assert metrics2.hit_ratio_percent == 10.0

    def test_initialize_global_tracker(self):
        """Test initializing global cache tracker."""
        import backend.src.observability.cache_tracking as cache_module

        tracker = initialize_cache_tracker()
        assert tracker is not None
        assert get_cache_tracker() == tracker


class TestCacheMetricsRecording:
    """Tests for recording metrics to Prometheus."""

    def test_record_cache_metrics(self):
        """Test recording cache metrics to Prometheus registry."""
        tracker = CacheTracker()
        tracker.record_hit("cache1")
        tracker.record_hit("cache1")
        tracker.record_miss("cache1")

        mock_registry = MagicMock()
        mock_registry.cache_hits_total = MagicMock()
        mock_registry.cache_misses_total = MagicMock()
        mock_registry.cache_hit_ratio = MagicMock()

        # Setup label mocking
        mock_registry.cache_hits_total.labels.return_value = MagicMock()
        mock_registry.cache_misses_total.labels.return_value = MagicMock()
        mock_registry.cache_hit_ratio.labels.return_value = MagicMock()

        # Patch global tracker
        import backend.src.observability.cache_tracking as cache_module

        cache_module._cache_tracker = tracker

        record_cache_metrics(mock_registry)

        # Verify metrics were recorded
        mock_registry.cache_hits_total.labels.assert_called()
        mock_registry.cache_misses_total.labels.assert_called()
        mock_registry.cache_hit_ratio.labels.assert_called()
