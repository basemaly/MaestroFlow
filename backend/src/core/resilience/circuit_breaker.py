"""
Circuit breaker pattern implementation with connection pool monitoring.

This module provides a generic circuit breaker for external service calls
with exponential backoff, metrics tracking, and connection pool health monitoring.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, Optional, TypeVar, Awaitable

from observability.metrics import (
    record_circuit_breaker_state_change,
    record_circuit_breaker_failure,
    record_circuit_breaker_success,
    record_circuit_breaker_open_duration,
    record_circuit_breaker_half_open_attempt,
    record_http_client_request,
    record_http_client_retry,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    # Failure thresholds
    failure_threshold: int = 5  # Open circuit after N consecutive failures
    success_threshold: int = 2  # Close circuit after N consecutive successes in half-open

    # Timing
    timeout: float = 30.0  # Request timeout in seconds
    reset_timeout: float = 60.0  # Time before trying half-open from open state

    # Retry strategy
    max_retries: int = 3
    retry_base_delay: float = 1.0  # Base delay for exponential backoff
    retry_max_delay: float = 30.0  # Maximum retry delay
    retry_jitter: bool = True  # Add random jitter to retry delays

    # Connection pool monitoring
    monitor_pool: bool = True
    pool_health_check_interval: float = 30.0  # How often to check pool health
    pool_max_connections: int = 100
    pool_max_keepalive: int = 50

    # Metrics
    enable_metrics: bool = True
    metrics_window_size: int = 100  # Keep last N requests for metrics


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker performance."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0  # Rejected due to open circuit
    timeouts: int = 0

    # Timing metrics (in seconds)
    total_response_time: float = 0.0
    min_response_time: Optional[float] = None
    max_response_time: Optional[float] = None

    # Circuit state changes
    state_changes: list = field(default_factory=list)
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None

    # Connection pool metrics
    active_connections: int = 0
    idle_connections: int = 0
    pending_requests: int = 0
    connection_errors: int = 0

    def record_request(self, duration: float, success: bool) -> None:
        """Record a request's outcome and duration."""
        self.total_requests += 1
        self.total_response_time += duration

        if self.min_response_time is None or duration < self.min_response_time:
            self.min_response_time = duration
        if self.max_response_time is None or duration > self.max_response_time:
            self.max_response_time = duration

        if success:
            self.successful_requests += 1
            self.last_success_time = datetime.now()
        else:
            self.failed_requests += 1
            self.last_failure_time = datetime.now()

    def get_success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100

    def get_avg_response_time(self) -> float:
        """Calculate average response time."""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    The circuit breaker prevents cascading failures by monitoring service health
    and temporarily blocking requests when the service is failing.
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.on_state_change = on_state_change

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state_changed_at = datetime.now()

        self.metrics = CircuitBreakerMetrics()
        self._lock = Lock()

        logger.info(f"Circuit breaker '{name}' initialized with config: {config}")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for automatic transitions."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                time_in_open = (datetime.now() - self._state_changed_at).total_seconds()
                if time_in_open >= self.config.reset_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
            return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.now()

        # Reset counters
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._failure_count = 0

        # Record state change
        self.metrics.state_changes.append(
            {
                "from": old_state.value,
                "to": new_state.value,
                "timestamp": self._state_changed_at.isoformat(),
            }
        )

        logger.info(f"Circuit breaker '{self.name}' state changed: {old_state.value} -> {new_state.value}")

        # Record Prometheus metrics
        try:
            record_circuit_breaker_state_change(
                service=self.name,
                from_state=old_state.value.upper(),
                to_state=new_state.value.upper(),
            )
        except Exception as e:
            logger.warning(f"Failed to record circuit breaker state change metric: {e}")

        if self.on_state_change:
            self.on_state_change(old_state, new_state)

    def _record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # Reset failure count on success

            # Record Prometheus metric
            try:
                record_circuit_breaker_success(service=self.name)
            except Exception as e:
                logger.warning(f"Failed to record circuit breaker success metric: {e}")

    def _record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

            # Record Prometheus metric
            try:
                record_circuit_breaker_failure(service=self.name)
            except Exception as e:
                logger.warning(f"Failed to record circuit breaker failure metric: {e}")

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitOpenError: If circuit is open
            TimeoutError: If request times out
            Exception: Any exception from func
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            self.metrics.rejected_requests += 1
            try:
                record_http_client_request(service=self.name, status="open", duration_seconds=0.0)
            except Exception as e:
                logger.warning(f"Failed to record circuit breaker open metric: {e}")
            raise CircuitOpenError(f"Circuit breaker '{self.name}' is OPEN")

        start_time = time.time()
        last_exception = None

        for attempt in range(self.config.max_retries):
            try:
                # Add timeout to the call
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)

                # Record success
                duration = time.time() - start_time
                self.metrics.record_request(duration, success=True)
                self._record_success()

                # Record Prometheus metric
                try:
                    record_http_client_request(service=self.name, status="success", duration_seconds=duration)
                except Exception as e:
                    logger.warning(f"Failed to record HTTP client request metric: {e}")

                return result

            except asyncio.TimeoutError as e:
                self.metrics.timeouts += 1
                last_exception = e
                logger.warning(f"Circuit breaker '{self.name}' timeout on attempt {attempt + 1}")
                # Record timeout metric
                try:
                    duration = time.time() - start_time
                    record_http_client_request(service=self.name, status="timeout", duration_seconds=duration)
                except Exception as ex:
                    logger.warning(f"Failed to record timeout metric: {ex}")

            except Exception as e:
                last_exception = e
                logger.warning(f"Circuit breaker '{self.name}' error on attempt {attempt + 1}: {e}")
                # Record failure metric
                try:
                    duration = time.time() - start_time
                    record_http_client_request(service=self.name, status="failure", duration_seconds=duration)
                except Exception as ex:
                    logger.warning(f"Failed to record failure metric: {ex}")

            # Calculate retry delay with exponential backoff
            if attempt < self.config.max_retries - 1:
                delay = min(
                    self.config.retry_base_delay * (2**attempt),
                    self.config.retry_max_delay,
                )

                # Add jitter if enabled
                if self.config.retry_jitter:
                    import random

                    delay *= 0.5 + random.random()

                # Record retry metric
                try:
                    record_http_client_retry(service=self.name)
                except Exception as e:
                    logger.warning(f"Failed to record retry metric: {e}")

                await asyncio.sleep(delay)

        # All retries failed
        duration = time.time() - start_time
        self.metrics.record_request(duration, success=False)
        self._record_failure()

        raise last_exception or Exception(f"Circuit breaker '{self.name}' failed after {self.config.max_retries} retries")

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status and metrics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "metrics": {
                    "total_requests": self.metrics.total_requests,
                    "success_rate": self.metrics.get_success_rate(),
                    "avg_response_time": self.metrics.get_avg_response_time(),
                    "rejected_requests": self.metrics.rejected_requests,
                    "timeouts": self.metrics.timeouts,
                    "active_connections": self.metrics.active_connections,
                    "idle_connections": self.metrics.idle_connections,
                },
                "last_failure": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
                "last_success": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
            }

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            logger.info(f"Circuit breaker '{self.name}' manually reset")

    def update_pool_metrics(self, active: int, idle: int, pending: int, errors: int = 0) -> None:
        """Update connection pool metrics."""
        if not self.config.monitor_pool:
            return

        with self._lock:
            self.metrics.active_connections = active
            self.metrics.idle_connections = idle
            self.metrics.pending_requests = pending
            self.metrics.connection_errors += errors

            # Check pool health
            total_connections = active + idle
            if total_connections >= self.config.pool_max_connections * 0.9:
                logger.warning(f"Connection pool for '{self.name}' near capacity: {total_connections}/{self.config.pool_max_connections}")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and rejecting requests."""

    pass
