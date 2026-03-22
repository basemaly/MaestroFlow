"""Monitoring and instrumentation for subagent execution performance."""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ExecutionMetric:
    """Single subagent execution metric."""

    task_id: str
    model_name: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    status: str = "pending"  # pending, running, completed, failed, timed_out
    queue_wait_seconds: float = 0.0

    @property
    def total_wait_and_execution(self) -> float:
        """Total time from submission to completion."""
        return self.queue_wait_seconds + self.duration_seconds


class SubagentMetricsCollector:
    """Collects and reports subagent execution metrics for bottleneck detection."""

    def __init__(self, max_history: int = 500):
        self.max_history = max_history
        self.metrics: deque[ExecutionMetric] = deque(maxlen=max_history)
        self.lock = threading.Lock()
        self.current_concurrent: int = 0
        self.max_concurrent_seen: int = 0

    def record_start(self, task_id: str, model_name: str, queue_wait_seconds: float = 0.0) -> ExecutionMetric:
        """Record the start of a subagent execution."""
        metric = ExecutionMetric(
            task_id=task_id,
            model_name=model_name,
            started_at=datetime.now(),
            queue_wait_seconds=queue_wait_seconds,
            status="running",
        )
        with self.lock:
            self.current_concurrent += 1
            self.max_concurrent_seen = max(self.max_concurrent_seen, self.current_concurrent)
        return metric

    def record_completion(self, metric: ExecutionMetric, status: str = "completed") -> None:
        """Record the completion of a subagent execution."""
        metric.completed_at = datetime.now()
        metric.duration_seconds = (metric.completed_at - metric.started_at).total_seconds()
        metric.status = status
        with self.lock:
            self.metrics.append(metric)
            self.current_concurrent = max(0, self.current_concurrent - 1)

    def get_summary(self, window_minutes: int = 5) -> dict:
        """Get execution metrics for the last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        with self.lock:
            recent = [m for m in self.metrics if m.completed_at and m.completed_at >= cutoff]

        if not recent:
            return {
                "window_minutes": window_minutes,
                "executions_count": 0,
                "avg_duration_seconds": 0.0,
                "max_duration_seconds": 0.0,
                "min_duration_seconds": 0.0,
                "avg_queue_wait_seconds": 0.0,
                "max_queue_wait_seconds": 0.0,
                "current_concurrent": self.current_concurrent,
                "max_concurrent_seen": self.max_concurrent_seen,
                "by_model": {},
                "warning_high_queue_wait": False,
                "warning_low_throughput": False,
            }

        durations = [m.duration_seconds for m in recent]
        queue_waits = [m.queue_wait_seconds for m in recent]
        models = {}
        for m in recent:
            if m.model_name not in models:
                models[m.model_name] = {"count": 0, "avg_duration": 0.0}
            models[m.model_name]["count"] += 1

        for model_name, data in models.items():
            model_metrics = [m for m in recent if m.model_name == model_name]
            data["avg_duration"] = sum(m.duration_seconds for m in model_metrics) / len(model_metrics)

        return {
            "window_minutes": window_minutes,
            "executions_count": len(recent),
            "avg_duration_seconds": sum(durations) / len(durations) if durations else 0.0,
            "max_duration_seconds": max(durations) if durations else 0.0,
            "min_duration_seconds": min(durations) if durations else 0.0,
            "avg_queue_wait_seconds": sum(queue_waits) / len(queue_waits) if queue_waits else 0.0,
            "max_queue_wait_seconds": max(queue_waits) if queue_waits else 0.0,
            "current_concurrent": self.current_concurrent,
            "max_concurrent_seen": self.max_concurrent_seen,
            "by_model": models,
            "warning_high_queue_wait": max(queue_waits) > 5.0 if queue_waits else False,
            "warning_low_throughput": len(recent) < 2 and window_minutes <= 5,
        }

    def log_summary(self) -> None:
        """Log a summary of recent metrics for debugging."""
        summary = self.get_summary()
        logger.info(
            "Subagent metrics (last 5 min): "
            f"executions={summary['executions_count']}, "
            f"avg_duration={summary['avg_duration_seconds']:.2f}s, "
            f"avg_queue_wait={summary['avg_queue_wait_seconds']:.2f}s, "
            f"current_concurrent={summary['current_concurrent']}, "
            f"max_concurrent_seen={summary['max_concurrent_seen']}"
        )
        if summary["warning_high_queue_wait"]:
            logger.warning(
                f"HIGH QUEUE WAIT DETECTED: max_queue_wait={summary['max_queue_wait_seconds']:.2f}s. "
                "This indicates thread pool saturation or model throttling."
            )
        if summary["executions_count"] > 0 and summary.get("warning_low_throughput"):
            logger.warning("LOW THROUGHPUT: Few executions in last 5 minutes. Check model/API availability.")


# Global collector instance
_metrics_collector = SubagentMetricsCollector()


def get_metrics_collector() -> SubagentMetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector


def record_subagent_start(task_id: str, model_name: str, queue_wait_seconds: float = 0.0) -> ExecutionMetric:
    """Record the start of a subagent execution."""
    return _metrics_collector.record_start(task_id, model_name, queue_wait_seconds)


def record_subagent_completion(metric: ExecutionMetric, status: str = "completed") -> None:
    """Record the completion of a subagent execution."""
    _metrics_collector.record_completion(metric, status)


def log_metrics_summary() -> None:
    """Log a summary of recent metrics."""
    _metrics_collector.log_summary()
