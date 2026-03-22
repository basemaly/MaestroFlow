"""
Tests for queue operation monitoring and latency tracking.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from backend.src.observability.queue_tracking import (
    QueueMetrics,
    QueueTracker,
    initialize_queue_tracker,
    get_queue_tracker,
    track_queue_operation,
    track_async_queue_operation,
    record_queue_metrics,
)


class TestQueueMetrics:
    """Tests for QueueMetrics dataclass."""

    def test_queue_metrics_creation(self):
        """Test creating queue metrics."""
        metrics = QueueMetrics(name="task_queue", max_depth=1000)
        assert metrics.name == "task_queue"
        assert metrics.max_depth == 1000
        assert metrics.processed_total == 0

    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        metrics = QueueMetrics(name="task_queue")
        metrics.processed_total = 100
        metrics.errors_total = 5

        assert metrics.error_rate == 5.0

    def test_error_rate_zero(self):
        """Test error rate when no items processed."""
        metrics = QueueMetrics(name="task_queue")
        assert metrics.error_rate == 0.0

    def test_latency_percentiles(self):
        """Test latency percentile calculations."""
        metrics = QueueMetrics(name="task_queue")

        # Add 100 latency measurements
        for i in range(100):
            metrics.record_latency(float(i) / 100.0)

        assert metrics.avg_latency > 0
        assert metrics.p95_latency > metrics.avg_latency
        assert metrics.p99_latency >= metrics.p95_latency

    def test_record_processed(self):
        """Test recording processed items."""
        metrics = QueueMetrics(name="task_queue")
        metrics.record_processed()
        metrics.record_processed()

        assert metrics.processed_total == 2

    def test_record_error(self):
        """Test recording errors."""
        metrics = QueueMetrics(name="task_queue")
        metrics.record_error()
        assert metrics.errors_total == 1

    def test_record_dlq_message(self):
        """Test recording DLQ messages."""
        metrics = QueueMetrics(name="task_queue")
        metrics.record_dlq_message()
        assert metrics.dlq_messages_total == 1


class TestQueueTracker:
    """Tests for QueueTracker class."""

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        tracker = QueueTracker(sla_p95_threshold_seconds=5.0)
        assert tracker.sla_threshold == 5.0
        assert len(tracker.queues) == 0

    def test_track_queue(self):
        """Test registering a queue."""
        tracker = QueueTracker()
        tracker.track_queue("task_queue", max_depth=1000)

        assert "task_queue" in tracker.queues
        assert tracker.queues["task_queue"].max_depth == 1000

    def test_record_queue_depth(self):
        """Test recording queue depth."""
        tracker = QueueTracker()
        tracker.record_queue_depth("task_queue", 50)
        tracker.record_queue_depth("task_queue", 75)

        assert tracker.get_queue_depth("task_queue") == 75

    def test_record_latency(self):
        """Test recording processing latency."""
        tracker = QueueTracker(sla_p95_threshold_seconds=5.0)
        tracker.record_latency("task_queue", 1.5)
        tracker.record_latency("task_queue", 2.0)

        metrics = tracker.get_metrics("task_queue")
        assert len(metrics.processing_latencies) == 2

    def test_record_processed(self):
        """Test recording processed items."""
        tracker = QueueTracker()
        tracker.record_processed("task_queue")
        tracker.record_processed("task_queue")

        metrics = tracker.get_metrics("task_queue")
        assert metrics.processed_total == 2

    def test_record_error(self):
        """Test recording errors."""
        tracker = QueueTracker()
        tracker.record_error("task_queue")
        tracker.record_error("task_queue")

        metrics = tracker.get_metrics("task_queue")
        assert metrics.errors_total == 2

    def test_record_dlq_message(self):
        """Test recording DLQ messages."""
        tracker = QueueTracker()
        tracker.record_dlq_message("task_queue")

        metrics = tracker.get_metrics("task_queue")
        assert metrics.dlq_messages_total == 1

    def test_health_status_healthy(self):
        """Test health status when healthy."""
        tracker = QueueTracker()
        tracker.track_queue("task_queue", max_depth=1000)
        tracker.record_queue_depth("task_queue", 100)
        tracker.record_latency("task_queue", 1.0)
        tracker.record_processed("task_queue")

        status, details = tracker.get_health_status()
        assert status == "healthy"

    def test_health_status_degraded_high_depth(self):
        """Test health status degraded when queue depth > 80%."""
        tracker = QueueTracker()
        tracker.track_queue("task_queue", max_depth=1000)
        tracker.record_queue_depth("task_queue", 850)

        status, details = tracker.get_health_status()
        assert status == "degraded"

    def test_health_status_degraded_high_error_rate(self):
        """Test health status degraded when error rate > 5%."""
        tracker = QueueTracker()
        tracker.track_queue("task_queue")

        # Create 20 processed items with 1 error (5%)
        for i in range(20):
            if i == 0:
                tracker.record_error("task_queue")
            else:
                tracker.record_processed("task_queue")

        tracker.record_processed("task_queue")  # Total of 20 successful

        status, details = tracker.get_health_status()
        assert status == "degraded"

    def test_health_status_degraded_sla_exceeded(self):
        """Test health status degraded when SLA exceeded."""
        tracker = QueueTracker(sla_p95_threshold_seconds=5.0)
        tracker.track_queue("task_queue")

        # Add latencies with p95 > 5 seconds
        for i in range(100):
            tracker.record_latency("task_queue", float(i) / 10.0)

        status, details = tracker.get_health_status()
        # p95 should be around 9.5 seconds
        assert status == "degraded"

    def test_get_all_metrics(self):
        """Test retrieving all queue metrics."""
        tracker = QueueTracker()
        tracker.track_queue("queue1")
        tracker.track_queue("queue2")

        all_metrics = tracker.get_all_metrics()
        assert len(all_metrics) == 2
        assert "queue1" in all_metrics
        assert "queue2" in all_metrics

    def test_clear_all(self):
        """Test clearing all metrics."""
        tracker = QueueTracker()
        tracker.track_queue("queue1")
        tracker.record_queue_depth("queue1", 50)

        tracker.clear_all()
        assert len(tracker.queues) == 0
        assert len(tracker._queue_depths) == 0


class TestQueueOperationContextManager:
    """Tests for queue operation context manager."""

    def test_successful_queue_operation(self):
        """Test context manager on successful operation."""
        tracker = QueueTracker()

        import backend.src.observability.queue_tracking as queue_module

        queue_module._queue_tracker = tracker

        with track_queue_operation("task_queue", "email_send"):
            time.sleep(0.01)

        metrics = tracker.get_metrics("task_queue")
        assert metrics.processed_total == 1
        assert metrics.errors_total == 0
        assert len(metrics.processing_latencies) == 1
        assert metrics.processing_latencies[0] >= 0.01

    def test_queue_operation_with_error(self):
        """Test context manager when operation fails."""
        tracker = QueueTracker()

        import backend.src.observability.queue_tracking as queue_module

        queue_module._queue_tracker = tracker

        try:
            with track_queue_operation("task_queue", "email_send"):
                raise ValueError("Processing failed")
        except ValueError:
            pass

        metrics = tracker.get_metrics("task_queue")
        assert metrics.processed_total == 0
        assert metrics.errors_total == 1
        assert len(metrics.processing_latencies) == 1

    @pytest.mark.asyncio
    async def test_async_queue_operation_success(self):
        """Test async context manager on successful operation."""
        tracker = QueueTracker()

        import backend.src.observability.queue_tracking as queue_module

        queue_module._queue_tracker = tracker

        async with track_async_queue_operation("task_queue", "email_send"):
            await asyncio.sleep(0.01)

        metrics = tracker.get_metrics("task_queue")
        assert metrics.processed_total == 1
        assert metrics.errors_total == 0

    @pytest.mark.asyncio
    async def test_async_queue_operation_error(self):
        """Test async context manager when operation fails."""
        tracker = QueueTracker()

        import backend.src.observability.queue_tracking as queue_module

        queue_module._queue_tracker = tracker

        try:
            async with track_async_queue_operation("task_queue", "email_send"):
                raise ValueError("Async processing failed")
        except ValueError:
            pass

        metrics = tracker.get_metrics("task_queue")
        assert metrics.processed_total == 0
        assert metrics.errors_total == 1


class TestQueueTrackerIntegration:
    """Integration tests for queue tracker."""

    def test_initialize_global_tracker(self):
        """Test initializing global queue tracker."""
        import backend.src.observability.queue_tracking as queue_module

        tracker = initialize_queue_tracker(sla_p95_threshold_seconds=5.0)
        assert tracker is not None
        assert get_queue_tracker() == tracker

    def test_complex_queue_scenario(self):
        """Test complex queue scenario with multiple operations."""
        tracker = QueueTracker()
        tracker.track_queue("task_queue", max_depth=1000)

        # Simulate queue activity
        for i in range(100):
            if i % 20 == 0:  # 5% error rate
                tracker.record_error("task_queue")
            else:
                tracker.record_processed("task_queue")

            # Record varying latencies
            tracker.record_latency("task_queue", 0.5 + (i % 5) * 0.1)

        # Simulate queue depth fluctuation
        tracker.record_queue_depth("task_queue", 150)

        status, details = tracker.get_health_status()
        queue_details = details["task_queue"]
        assert queue_details["processed_total"] == 95
        assert queue_details["errors_total"] == 5


class TestQueueMetricsRecording:
    """Tests for recording metrics to Prometheus."""

    def test_record_queue_metrics(self):
        """Test recording queue metrics to Prometheus registry."""
        tracker = QueueTracker()
        tracker.track_queue("task_queue", max_depth=1000)
        tracker.record_queue_depth("task_queue", 250)

        mock_registry = MagicMock()
        mock_registry.record_queue_depth = MagicMock()

        import backend.src.observability.queue_tracking as queue_module

        queue_module._queue_tracker = tracker

        record_queue_metrics(mock_registry)

        mock_registry.record_queue_depth.assert_called_with("task_queue", 250)


# Import asyncio for async tests
import asyncio
