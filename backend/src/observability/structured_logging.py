"""
Structured logging for resilience events.

Provides structured event logging for circuit breakers, connection pools,
and subagent pool management. Integrates with observability platforms
for centralized monitoring and audit trails.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EventSeverity(Enum):
    """Severity level for resilience events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventCategory(Enum):
    """Category of resilience event."""

    CIRCUIT_BREAKER = "circuit_breaker"
    CONNECTION_POOL = "connection_pool"
    SUBAGENT_POOL = "subagent_pool"
    HTTP_REQUEST = "http_request"
    SYSTEM_RESOURCE = "system_resource"
    POOL_ADJUSTMENT = "pool_adjustment"


@dataclass
class ResilientEvent:
    """Structured event for resilience monitoring."""

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    event_id: str = ""  # Set by logger
    category: EventCategory = EventCategory.CIRCUIT_BREAKER
    severity: EventSeverity = EventSeverity.INFO
    service: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    trace_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["category"] = self.category.value
        data["severity"] = self.severity.value
        return data


class StructuredLogger:
    """Logger for resilience events with structured output."""

    def __init__(self, name: str = "maestroflow.resilience"):
        self.logger = logging.getLogger(name)
        self._event_counter = 0

    def _log_event(self, event: ResilientEvent) -> None:
        """Log a structured event."""
        self._event_counter += 1
        event.event_id = f"evt-{self._event_counter:08d}"

        log_method = getattr(self.logger, event.severity.value, self.logger.info)
        log_method(event.message, extra={"event": event.to_dict()})

    # Circuit Breaker Events

    def circuit_opened(
        self,
        service: str,
        failure_count: int,
        failure_threshold: int,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when circuit breaker opens."""
        event = ResilientEvent(
            category=EventCategory.CIRCUIT_BREAKER,
            severity=EventSeverity.WARNING,
            service=service,
            message=f"Circuit breaker opened for {service}",
            details={
                "transition": "CLOSED -> OPEN",
                "failure_count": failure_count,
                "failure_threshold": failure_threshold,
            },
            trace_id=trace_id,
        )
        self._log_event(event)

    def circuit_closed(
        self,
        service: str,
        success_count: int,
        success_threshold: int,
        duration_open_seconds: float,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when circuit breaker closes."""
        event = ResilientEvent(
            category=EventCategory.CIRCUIT_BREAKER,
            severity=EventSeverity.INFO,
            service=service,
            message=f"Circuit breaker closed for {service}",
            details={
                "transition": "HALF_OPEN -> CLOSED",
                "success_count": success_count,
                "success_threshold": success_threshold,
                "was_open_for_seconds": duration_open_seconds,
            },
            duration_ms=duration_open_seconds * 1000,
            trace_id=trace_id,
        )
        self._log_event(event)

    def circuit_half_open(
        self,
        service: str,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when circuit breaker transitions to half-open."""
        event = ResilientEvent(
            category=EventCategory.CIRCUIT_BREAKER,
            severity=EventSeverity.INFO,
            service=service,
            message=f"Circuit breaker half-open for {service}",
            details={"transition": "OPEN -> HALF_OPEN"},
            trace_id=trace_id,
        )
        self._log_event(event)

    def circuit_failure_recorded(
        self,
        service: str,
        failure_count: int,
        error: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when a failure is recorded by circuit breaker."""
        event = ResilientEvent(
            category=EventCategory.CIRCUIT_BREAKER,
            severity=EventSeverity.WARNING,
            service=service,
            message=f"Failure recorded for {service}",
            details={"failure_count": failure_count},
            error=error,
            trace_id=trace_id,
        )
        self._log_event(event)

    def circuit_success_recorded(
        self,
        service: str,
        success_count: int,
        duration_ms: float,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when a success is recorded by circuit breaker."""
        event = ResilientEvent(
            category=EventCategory.CIRCUIT_BREAKER,
            severity=EventSeverity.DEBUG,
            service=service,
            message=f"Success recorded for {service}",
            details={"success_count": success_count},
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        self._log_event(event)

    def circuit_rejected_request(
        self,
        service: str,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when a request is rejected due to open circuit."""
        event = ResilientEvent(
            category=EventCategory.CIRCUIT_BREAKER,
            severity=EventSeverity.WARNING,
            service=service,
            message=f"Request rejected: circuit breaker open for {service}",
            details={"reason": "circuit_open"},
            trace_id=trace_id,
        )
        self._log_event(event)

    # HTTP Request Events

    def http_request_timeout(
        self,
        service: str,
        timeout_seconds: float,
        attempt: int,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when an HTTP request times out."""
        event = ResilientEvent(
            category=EventCategory.HTTP_REQUEST,
            severity=EventSeverity.WARNING,
            service=service,
            message=f"HTTP request timeout for {service}",
            details={
                "timeout_seconds": timeout_seconds,
                "attempt": attempt,
            },
            trace_id=trace_id,
        )
        self._log_event(event)

    def http_request_retry(
        self,
        service: str,
        attempt: int,
        delay_seconds: float,
        reason: str,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when an HTTP request is retried."""
        event = ResilientEvent(
            category=EventCategory.HTTP_REQUEST,
            severity=EventSeverity.DEBUG,
            service=service,
            message=f"Retrying HTTP request for {service}",
            details={
                "attempt": attempt,
                "delay_seconds": delay_seconds,
                "reason": reason,
            },
            trace_id=trace_id,
        )
        self._log_event(event)

    def http_request_failed(
        self,
        service: str,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when an HTTP request fails after all retries."""
        event = ResilientEvent(
            category=EventCategory.HTTP_REQUEST,
            severity=EventSeverity.ERROR,
            service=service,
            message=f"HTTP request failed for {service}",
            details={
                "status_code": status_code,
            },
            duration_ms=duration_ms,
            error=error,
            trace_id=trace_id,
        )
        self._log_event(event)

    def http_request_success(
        self,
        service: str,
        status_code: int,
        duration_ms: float,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log a successful HTTP request."""
        event = ResilientEvent(
            category=EventCategory.HTTP_REQUEST,
            severity=EventSeverity.DEBUG,
            service=service,
            message=f"HTTP request succeeded for {service}",
            details={"status_code": status_code},
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        self._log_event(event)

    # Subagent Pool Events

    def pool_size_adjusted(
        self,
        old_size: int,
        new_size: int,
        direction: str,
        reason: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log when subagent pool size is adjusted."""
        severity = EventSeverity.INFO if direction in ["up", "down"] else EventSeverity.DEBUG
        event = ResilientEvent(
            category=EventCategory.POOL_ADJUSTMENT,
            severity=severity,
            message=f"Subagent pool adjusted {direction}: {old_size} -> {new_size}",
            details={
                "old_size": old_size,
                "new_size": new_size,
                "direction": direction,
                "reason": reason,
                **(metrics or {}),
            },
        )
        self._log_event(event)

    def pool_worker_started(self, worker_id: str) -> None:
        """Log when a pool worker is started."""
        event = ResilientEvent(
            category=EventCategory.SUBAGENT_POOL,
            severity=EventSeverity.DEBUG,
            message=f"Subagent worker started: {worker_id}",
            details={"worker_id": worker_id},
        )
        self._log_event(event)

    def pool_worker_stopped(self, worker_id: str, reason: str) -> None:
        """Log when a pool worker is stopped."""
        event = ResilientEvent(
            category=EventCategory.SUBAGENT_POOL,
            severity=EventSeverity.INFO,
            message=f"Subagent worker stopped: {worker_id}",
            details={
                "worker_id": worker_id,
                "reason": reason,
            },
        )
        self._log_event(event)

    def subagent_task_started(
        self,
        task_id: str,
        task_name: str,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when a subagent task starts."""
        event = ResilientEvent(
            category=EventCategory.SUBAGENT_POOL,
            severity=EventSeverity.DEBUG,
            message=f"Subagent task started: {task_name}",
            details={
                "task_id": task_id,
                "task_name": task_name,
            },
            trace_id=trace_id,
        )
        self._log_event(event)

    def subagent_task_completed(
        self,
        task_id: str,
        task_name: str,
        status: str,
        duration_ms: float,
        trace_id: Optional[str] = None,
    ) -> None:
        """Log when a subagent task completes."""
        severity = EventSeverity.ERROR if status == "failed" else EventSeverity.DEBUG
        event = ResilientEvent(
            category=EventCategory.SUBAGENT_POOL,
            severity=severity,
            message=f"Subagent task completed: {task_name} ({status})",
            details={
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
            },
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        self._log_event(event)

    def subagent_queue_backlog(
        self,
        queue_depth: int,
        pool_size: int,
        active_workers: int,
    ) -> None:
        """Log when subagent queue has significant backlog."""
        event = ResilientEvent(
            category=EventCategory.SUBAGENT_POOL,
            severity=EventSeverity.WARNING,
            message="Subagent queue backlog detected",
            details={
                "queue_depth": queue_depth,
                "pool_size": pool_size,
                "active_workers": active_workers,
                "ratio": queue_depth / max(1, pool_size),
            },
        )
        self._log_event(event)

    # System Resource Events

    def high_cpu_usage(self, cpu_percent: float, threshold: float) -> None:
        """Log when system CPU usage is high."""
        severity = EventSeverity.CRITICAL if cpu_percent > 95 else EventSeverity.WARNING
        event = ResilientEvent(
            category=EventCategory.SYSTEM_RESOURCE,
            severity=severity,
            message=f"High CPU usage: {cpu_percent:.1f}%",
            details={
                "cpu_percent": cpu_percent,
                "threshold": threshold,
            },
        )
        self._log_event(event)

    def high_memory_usage(self, memory_percent: float, threshold: float) -> None:
        """Log when system memory usage is high."""
        severity = EventSeverity.CRITICAL if memory_percent > 95 else EventSeverity.WARNING
        event = ResilientEvent(
            category=EventCategory.SYSTEM_RESOURCE,
            severity=severity,
            message=f"High memory usage: {memory_percent:.1f}%",
            details={
                "memory_percent": memory_percent,
                "threshold": threshold,
            },
        )
        self._log_event(event)

    def resource_constrained(
        self,
        cpu_percent: float,
        memory_percent: float,
        action_taken: str,
    ) -> None:
        """Log when system resources are constrained and action is taken."""
        event = ResilientEvent(
            category=EventCategory.SYSTEM_RESOURCE,
            severity=EventSeverity.WARNING,
            message="System resources constrained, action taken",
            details={
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "action": action_taken,
            },
        )
        self._log_event(event)


# Global logger instance
_logger: Optional[StructuredLogger] = None


def get_structured_logger() -> StructuredLogger:
    """Get or create the global structured logger."""
    global _logger
    if _logger is None:
        _logger = StructuredLogger()
    return _logger
