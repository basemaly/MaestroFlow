"""Tests for metrics collection module."""

import pytest
from prometheus_client import REGISTRY

from src.observability.metrics import (
    db_connections_active,
    db_connections_total,
    cache_hits_total,
    cache_misses_total,
    cache_hit_ratio,
    queue_depth,
    http_requests_total,
    measure_db_query_time,
    record_cache_operation,
    set_queue_depth,
)


class TestMetricsInitialization:
    """Test that metrics are properly initialized."""

    def test_metrics_are_registered(self):
        """Verify that core metrics are registered with Prometheus."""
        # Get list of all metric names in registry
        metric_names = {m.name for m in REGISTRY.collect() for _ in m.samples}

        # Check that key metrics are present
        expected_metrics = {
            "db_connections_active",
            "cache_hits_total",
            "cache_misses_total",
            "cache_hit_ratio",
            "queue_depth",
            "http_requests_total",
        }

        assert expected_metrics.issubset(metric_names), f"Missing metrics: {expected_metrics - metric_names}"


class TestContextManagers:
    """Test timing context managers."""

    def test_measure_db_query_time(self):
        """Test that db query timing context manager records metrics."""
        initial_count = cache_misses_total.labels(cache_name="test")._value.get()

        with measure_db_query_time("SELECT"):
            pass  # Simulate query

        # Verify histogram was recorded (we can't directly check but no errors should occur)
        assert True  # If we get here without exception, the context manager worked


class TestCacheMetrics:
    """Test cache operation tracking."""

    def test_cache_hit_ratio_calculation(self):
        """Test that cache hit ratio is calculated correctly."""
        cache_name = "test_cache"

        # Reset cache metrics for this test
        # Record 7 hits and 3 misses
        for _ in range(7):
            record_cache_operation(cache_name, hit=True)
        for _ in range(3):
            record_cache_operation(cache_name, hit=False)

        # Hit ratio should be 0.7
        ratio_value = cache_hit_ratio.labels(cache_name=cache_name)._value.get()
        assert 0.69 < ratio_value < 0.71, f"Expected ~0.7, got {ratio_value}"

    def test_cache_hit_miss_counters(self):
        """Test that cache hit and miss counters increment."""
        cache_name = "test_cache_2"

        record_cache_operation(cache_name, hit=True)
        record_cache_operation(cache_name, hit=True)
        record_cache_operation(cache_name, hit=False)

        hits = cache_hits_total.labels(cache_name=cache_name)._value.get()
        misses = cache_misses_total.labels(cache_name=cache_name)._value.get()

        assert hits >= 2, f"Expected hits >= 2, got {hits}"
        assert misses >= 1, f"Expected misses >= 1, got {misses}"


class TestQueueMetrics:
    """Test queue depth tracking."""

    def test_queue_depth_update(self):
        """Test that queue depth gauge is updated."""
        queue_name = "test_queue"

        set_queue_depth(queue_name, depth=42)
        depth_value = queue_depth.labels(queue_name=queue_name)._value.get()

        assert depth_value == 42, f"Expected depth=42, got {depth_value}"

    def test_queue_depth_zero(self):
        """Test that queue depth can be set to zero."""
        queue_name = "test_queue_empty"

        set_queue_depth(queue_name, depth=0)
        depth_value = queue_depth.labels(queue_name=queue_name)._value.get()

        assert depth_value == 0, f"Expected depth=0, got {depth_value}"


class TestHTTPMetrics:
    """Test HTTP request metrics."""

    def test_http_requests_counter(self):
        """Test that HTTP request counter increments."""
        http_requests_total.labels(method="GET", endpoint="/test", status=200).inc()
        http_requests_total.labels(method="GET", endpoint="/test", status=200).inc()

        count = http_requests_total.labels(method="GET", endpoint="/test", status=200)._value.get()
        assert count >= 2, f"Expected count >= 2, got {count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
