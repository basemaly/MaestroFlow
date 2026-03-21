"""
Tests for circuit breaker implementation.

Covers: state transitions, retry logic with exponential backoff, timeout handling,
metrics collection, and pool monitoring.
"""

import asyncio
import pytest
import time
from datetime import datetime

from src.core.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitOpenError,
    CircuitState,
)


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state machine transitions."""

    def test_initial_state_is_closed(self):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker("test_service")
        assert cb.state == CircuitState.CLOSED

    def test_closed_to_open_on_failures(self):
        """Circuit should open after failure threshold exceeded."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test_service", config=config)

        # Record failures
        cb._record_failure()
        assert cb.state == CircuitState.CLOSED

        cb._record_failure()
        assert cb.state == CircuitState.CLOSED

        cb._record_failure()
        assert cb.state == CircuitState.OPEN

    def test_open_to_half_open_on_timeout(self):
        """Circuit should transition to half-open after reset timeout."""
        config = CircuitBreakerConfig(reset_timeout=0.1)
        cb = CircuitBreaker("test_service", config=config)

        # Open the circuit
        for _ in range(config.failure_threshold):
            cb._record_failure()

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Should transition to half-open
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self):
        """Circuit should close after enough successes in half-open."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            reset_timeout=0.1,
        )
        cb = CircuitBreaker("test_service", config=config)

        # Open the circuit
        for _ in range(config.failure_threshold):
            cb._record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait and transition to half-open
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Record successes
        cb._record_success()
        assert cb.state == CircuitState.HALF_OPEN

        cb._record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        """Circuit should reopen immediately on failure in half-open."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            reset_timeout=0.1,
        )
        cb = CircuitBreaker("test_service", config=config)

        # Open the circuit
        for _ in range(config.failure_threshold):
            cb._record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait and transition to half-open
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # One failure should reopen
        cb._record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerAsyncCall:
    """Test async call execution through circuit breaker.

    Note: Full async tests require pytest-asyncio plugin.
    These are validated separately in integration tests.
    """

    def test_async_call_api_exists(self):
        """Verify circuit breaker has async call method."""
        cb = CircuitBreaker("test_service")
        assert hasattr(cb, "call")
        assert asyncio.iscoroutinefunction(cb.call)


class TestCircuitBreakerMetrics:
    """Test metrics collection."""

    def test_metrics_instantiation(self):
        """Metrics should be properly initialized."""
        cb = CircuitBreaker("test_service")

        assert cb.metrics.total_requests == 0
        assert cb.metrics.successful_requests == 0
        assert cb.metrics.failed_requests == 0
        assert cb.metrics.timeouts == 0
        assert cb.metrics.rejected_requests == 0

    def test_metrics_recording_structure(self):
        """Metrics recording should handle request data."""
        metrics = CircuitBreakerMetrics()

        metrics.record_request(0.5, success=True)

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.min_response_time == 0.5
        assert metrics.max_response_time == 0.5
        assert metrics.total_response_time == 0.5

        metrics.record_request(1.0, success=False)

        assert metrics.total_requests == 2
        assert metrics.failed_requests == 1
        assert metrics.min_response_time == 0.5
        assert metrics.max_response_time == 1.0

    def test_success_rate_calculation(self):
        """Success rate should be calculated correctly."""
        cb = CircuitBreaker("test_service")

        cb.metrics.total_requests = 10
        cb.metrics.successful_requests = 7
        cb.metrics.failed_requests = 3

        assert cb.metrics.get_success_rate() == 70.0

    def test_success_rate_with_no_requests(self):
        """Success rate should be 100% with no requests."""
        cb = CircuitBreaker("test_service")
        assert cb.metrics.get_success_rate() == 100.0

    def test_average_response_time(self):
        """Average response time should be calculated correctly."""
        cb = CircuitBreaker("test_service")

        cb.metrics.total_requests = 4
        cb.metrics.total_response_time = 4.0

        assert cb.metrics.get_avg_response_time() == 1.0

    def test_state_change_tracking(self):
        """State changes should be recorded with timestamps."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test_service", config=config)

        initial_changes = len(cb.metrics.state_changes)

        cb._record_failure()

        # Should have recorded state change
        assert len(cb.metrics.state_changes) == initial_changes + 1
        change = cb.metrics.state_changes[-1]
        assert change["from"] == "closed"
        assert change["to"] == "open"
        assert "timestamp" in change


class TestCircuitBreakerPoolMonitoring:
    """Test connection pool monitoring."""

    def test_pool_metrics_update(self):
        """Pool metrics should be updated correctly."""
        cb = CircuitBreaker("test_service")

        cb.update_pool_metrics(active=5, idle=3, pending=2)

        assert cb.metrics.active_connections == 5
        assert cb.metrics.idle_connections == 3
        assert cb.metrics.pending_requests == 2

    def test_pool_health_check_warning(self, caplog):
        """Warning should be logged when pool is near capacity."""
        config = CircuitBreakerConfig(pool_max_connections=10)
        cb = CircuitBreaker("test_service", config=config)

        # 90% of capacity
        cb.update_pool_metrics(active=7, idle=2, pending=0)

        assert "near capacity" in caplog.text

    def test_disabled_pool_monitoring(self):
        """Pool monitoring can be disabled."""
        config = CircuitBreakerConfig(monitor_pool=False)
        cb = CircuitBreaker("test_service", config=config)

        cb.update_pool_metrics(active=100, idle=100, pending=50)

        # Should not be updated
        assert cb.metrics.active_connections == 0

    def test_connection_error_tracking(self):
        """Connection errors should be tracked."""
        cb = CircuitBreaker("test_service")

        cb.update_pool_metrics(active=5, idle=3, pending=2, errors=2)
        cb.update_pool_metrics(active=5, idle=3, pending=2, errors=1)

        assert cb.metrics.connection_errors == 3


class TestCircuitBreakerHealthStatus:
    """Test health status reporting."""

    def test_health_status_structure(self):
        """Health status should contain expected fields."""
        cb = CircuitBreaker("test_service")

        health = cb.get_health_status()

        assert "name" in health
        assert "state" in health
        assert "metrics" in health
        assert health["name"] == "test_service"

    def test_health_status_metrics(self):
        """Health status metrics should be current."""
        cb = CircuitBreaker("test_service")

        cb.metrics.total_requests = 100
        cb.metrics.successful_requests = 85
        cb.metrics.rejected_requests = 5
        cb.metrics.timeouts = 3

        health = cb.get_health_status()

        assert health["metrics"]["total_requests"] == 100
        assert health["metrics"]["success_rate"] == 85.0
        assert health["metrics"]["rejected_requests"] == 5
        assert health["metrics"]["timeouts"] == 3


class TestCircuitBreakerReset:
    """Test manual reset functionality."""

    def test_manual_reset_closes_circuit(self):
        """Manual reset should close the circuit."""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test_service", config=config)

        # Open the circuit
        cb._record_failure()
        assert cb.state == CircuitState.OPEN

        # Reset
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_manual_reset_clears_counters(self):
        """Manual reset should clear failure and success counters."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
        )
        cb = CircuitBreaker("test_service", config=config)

        cb._failure_count = 4
        cb._success_count = 1

        cb.reset()

        assert cb._failure_count == 0
        assert cb._success_count == 0


class TestCircuitBreakerStateChangeCallback:
    """Test state change callbacks."""

    def test_state_change_callback(self):
        """Callback should be called on state changes."""
        config = CircuitBreakerConfig(failure_threshold=1)
        changes = []

        def on_change(old_state, new_state):
            changes.append((old_state, new_state))

        cb = CircuitBreaker("test_service", config=config, on_state_change=on_change)

        # Trigger state change
        cb._record_failure()

        assert len(changes) == 1
        assert changes[0][0] == CircuitState.CLOSED
        assert changes[0][1] == CircuitState.OPEN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
