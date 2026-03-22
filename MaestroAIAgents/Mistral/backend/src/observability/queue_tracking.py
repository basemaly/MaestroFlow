"""
Queue operation monitoring and latency tracking for MaestroFlow.

Provides:
- Queue depth tracking
- Processing latency monitoring (with SLA thresholds)
- Error rate tracking
- Dead-letter queue monitoring
- Context manager for queue operations
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class QueueMetrics:
    """Metrics for a single queue."""

    name: str
    max_depth: Optional[int] = None
    processed_total: int = 0
    errors_total: int = 0
    dlq_messages_total: int = 0

    # Latency tracking (simplified - in production use histogram)
    processing_latencies: list[float] = field(default_factory=list)
    _max_latencies_stored: int = 1000

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.processed_total == 0:
            return 0.0
        return (self.errors_total / self.processed_total) * 100

    @property
    def avg_latency(self) -> float:
        """Calculate average processing latency."""
        if not self.processing_latencies:
            return 0.0
        return sum(self.processing_latencies) / len(self.processing_latencies)

    @property
    def p95_latency(self) -> float:
        """Calculate 95th percentile latency."""
        if not self.processing_latencies:
            return 0.0
        sorted_latencies = sorted(self.processing_latencies)
        p95_index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[p95_index]

    @property
    def p99_latency(self) -> float:
        """Calculate 99th percentile latency."""
        if not self.processing_latencies:
            return 0.0
        sorted_latencies = sorted(self.processing_latencies)
        p99_index = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[p99_index]

    def record_latency(self, latency: float) -> None:
        """Record a processing latency measurement."""
        self.processing_latencies.append(latency)
        # Keep only recent latencies to avoid unbounded growth
        if len(self.processing_latencies) > self._max_latencies_stored:
            self.processing_latencies.pop(0)

    def record_processed(self) -> None:
        """Record successful processing of a queue item."""
        self.processed_total += 1

    def record_error(self) -> None:
        """Record processing error."""
        self.errors_total += 1

    def record_dlq_message(self) -> None:
        """Record a message moved to dead-letter queue."""
        self.dlq_messages_total += 1


class QueueTracker:
    """
    Centralized queue operation tracker.

    Tracks multiple queues, calculates latency percentiles, and monitors error rates.
    """

    def __init__(self, sla_p95_threshold_seconds: float = 5.0):
        """
        Initialize queue tracker.

        Args:
            sla_p95_threshold_seconds: SLA threshold for 95th percentile latency
        """
        self.queues: dict[str, QueueMetrics] = {}
        self.sla_threshold = sla_p95_threshold_seconds
        self._queue_depths: dict[str, int] = {}

    def track_queue(self, queue_name: str, max_depth: Optional[int] = None) -> None:
        """Register a queue for tracking."""
        if queue_name not in self.queues:
            self.queues[queue_name] = QueueMetrics(name=queue_name, max_depth=max_depth)

    def record_queue_depth(self, queue_name: str, depth: int) -> None:
        """Record current queue depth."""
        if queue_name not in self.queues:
            self.track_queue(queue_name)
        self._queue_depths[queue_name] = depth

    def get_queue_depth(self, queue_name: str) -> int:
        """Get current queue depth."""
        return self._queue_depths.get(queue_name, 0)

    def record_latency(self, queue_name: str, latency: float) -> None:
        """Record processing latency for a queue item."""
        if queue_name not in self.queues:
            self.track_queue(queue_name)

        metrics = self.queues[queue_name]
        metrics.record_latency(latency)

        # Check SLA compliance
        if metrics.p95_latency > self.sla_threshold:
            logger.warning(
                f"Queue '{queue_name}' p95 latency {metrics.p95_latency:.2f}s "
                f"exceeds SLA threshold {self.sla_threshold}s"
            )

    def record_processed(self, queue_name: str) -> None:
        """Record successful processing of a queue item."""
        if queue_name not in self.queues:
            self.track_queue(queue_name)
        self.queues[queue_name].record_processed()

    def record_error(self, queue_name: str) -> None:
        """Record processing error for a queue item."""
        if queue_name not in self.queues:
            self.track_queue(queue_name)
        self.queues[queue_name].record_error()

    def record_dlq_message(self, queue_name: str) -> None:
        """Record a message moved to dead-letter queue."""
        if queue_name not in self.queues:
            self.track_queue(queue_name)
        self.queues[queue_name].record_dlq_message()

    def get_metrics(self, queue_name: str) -> Optional[QueueMetrics]:
        """Get metrics for a specific queue."""
        return self.queues.get(queue_name)

    def get_all_metrics(self) -> dict[str, QueueMetrics]:
        """Get metrics for all registered queues."""
        return dict(self.queues)

    def get_health_status(self) -> tuple[str, dict]:
        """
        Get overall queue health status.

        Returns:
            Tuple of (status, details) where status is 'healthy', 'degraded', or 'unhealthy'
        """
        if not self.queues:
            return "healthy", {}

        details = {}
        worst_status = "healthy"

        for queue_name, metrics in self.queues.items():
            depth = self.get_queue_depth(queue_name)
            depth_percent = (
                (depth / metrics.max_depth * 100) if metrics.max_depth else 0
            )

            queue_detail = {
                "depth": depth,
                "max_depth": metrics.max_depth,
                "depth_percent": round(depth_percent, 1) if metrics.max_depth else None,
                "processed_total": metrics.processed_total,
                "errors_total": metrics.errors_total,
                "error_rate_percent": round(metrics.error_rate, 1),
                "avg_latency_sec": round(metrics.avg_latency, 3),
                "p95_latency_sec": round(metrics.p95_latency, 3),
                "p99_latency_sec": round(metrics.p99_latency, 3),
                "dlq_messages": metrics.dlq_messages_total,
            }
            details[queue_name] = queue_detail

            # Determine queue status
            queue_status = "healthy"

            # Check error rate
            if metrics.error_rate > 5:
                queue_status = "degraded"

            # Check SLA compliance
            if metrics.p95_latency > self.sla_threshold:
                queue_status = "degraded"

            # Check queue depth (if max capacity known)
            if metrics.max_depth and depth > (metrics.max_depth * 0.8):
                queue_status = "degraded"

            # Track worst status
            if queue_status == "degraded" and worst_status != "unhealthy":
                worst_status = "degraded"

        return worst_status, details

    def clear_all(self) -> None:
        """Clear all queue metrics (useful for testing)."""
        self.queues.clear()
        self._queue_depths.clear()


# Global queue tracker instance
_queue_tracker: Optional[QueueTracker] = None


def initialize_queue_tracker(sla_p95_threshold_seconds: float = 5.0) -> QueueTracker:
    """
    Initialize global queue tracker.

    Args:
        sla_p95_threshold_seconds: SLA threshold for 95th percentile latency

    Returns:
        Initialized QueueTracker instance
    """
    global _queue_tracker
    _queue_tracker = QueueTracker(sla_p95_threshold_seconds=sla_p95_threshold_seconds)
    logger.info("Queue tracker initialized")
    return _queue_tracker


def get_queue_tracker() -> Optional[QueueTracker]:
    """Get the global queue tracker instance."""
    return _queue_tracker


@contextmanager
def track_queue_operation(
    queue_name: str = "default",
    task_type: str = "unknown",
    metrics_registry=None,
):
    """
    Context manager to transparently track queue operations.

    Args:
        queue_name: Name of the queue
        task_type: Type of task being processed
        metrics_registry: Optional MetricsRegistry for Prometheus integration

    Example:
        with track_queue_operation('task_queue', 'email_send'):
            process_task(task)
    """
    tracker = get_queue_tracker()
    if tracker:
        tracker.track_queue(queue_name)

    start_time = time.time()
    error_occurred = False

    try:
        yield
    except Exception as e:
        error_occurred = True
        if tracker:
            tracker.record_error(queue_name)
        raise
    finally:
        duration = time.time() - start_time

        if tracker:
            if not error_occurred:
                tracker.record_processed(queue_name)
            tracker.record_latency(queue_name, duration)

        if metrics_registry:
            metrics_registry.queue_processing_latency_seconds.labels(
                queue_name=queue_name
            ).observe(duration)
            if not error_occurred:
                metrics_registry.increment_queue_processed(queue_name)


@asynccontextmanager
async def track_async_queue_operation(
    queue_name: str = "default",
    task_type: str = "unknown",
    metrics_registry=None,
):
    """
    Async context manager to transparently track async queue operations.

    Args:
        queue_name: Name of the queue
        task_type: Type of task being processed
        metrics_registry: Optional MetricsRegistry for Prometheus integration

    Example:
        async with track_async_queue_operation('task_queue', 'email_send'):
            await process_task(task)
    """
    tracker = get_queue_tracker()
    if tracker:
        tracker.track_queue(queue_name)

    start_time = time.time()
    error_occurred = False

    try:
        yield
    except Exception as e:
        error_occurred = True
        if tracker:
            tracker.record_error(queue_name)
        raise
    finally:
        duration = time.time() - start_time

        if tracker:
            if not error_occurred:
                tracker.record_processed(queue_name)
            tracker.record_latency(queue_name, duration)

        if metrics_registry:
            metrics_registry.queue_processing_latency_seconds.labels(
                queue_name=queue_name
            ).observe(duration)
            if not error_occurred:
                metrics_registry.increment_queue_processed(queue_name)


def record_queue_metrics(metrics_registry) -> None:
    """
    Record current queue metrics to Prometheus.

    Args:
        metrics_registry: MetricsRegistry instance
    """
    tracker = get_queue_tracker()
    if not tracker:
        return

    for queue_name, depth in tracker._queue_depths.items():
        metrics_registry.record_queue_depth(queue_name, depth)
