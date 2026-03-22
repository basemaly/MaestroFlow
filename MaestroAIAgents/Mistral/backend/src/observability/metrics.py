"""
Prometheus metrics infrastructure for MaestroFlow observability.

Provides metrics collection for:
- Connection pool monitoring (active connections, wait times, reuse)
- Database query latency tracking
- Queue depth and processing latency
- Cache hit/miss ratios
- WebSocket connection lifecycle and messaging
- Process memory and CPU usage
- HTTP request/response metrics
"""

from contextlib import contextmanager
from typing import Optional, Dict, Any
import time
import logging

from prometheus_client import Counter, Gauge, Histogram, Summary

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """Central registry for all Prometheus metrics."""

    def __init__(self):
        """Initialize all metric collectors."""

        # ============ CONNECTION POOL METRICS ============
        self.db_connections_active = Gauge(
            "db_connections_active", "Current number of active connections in pool"
        )

        self.db_connections_total = Counter(
            "db_connections_total", "Total connections created"
        )

        self.db_connections_reused = Counter(
            "db_connections_reused", "Total times connection was reused"
        )

        self.db_connection_wait_seconds = Histogram(
            "db_connection_wait_seconds",
            "Time spent waiting for available connection",
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        )

        # ============ DATABASE QUERY METRICS ============
        self.db_query_duration_seconds = Histogram(
            "db_query_duration_seconds",
            "Query execution time in seconds",
            labelnames=["query_type"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        )

        # ============ QUEUE METRICS ============
        self.queue_depth = Gauge(
            "queue_depth", "Current number of items in queue", labelnames=["queue_name"]
        )

        self.queue_processed_total = Counter(
            "queue_processed_total",
            "Total items processed from queue",
            labelnames=["queue_name"],
        )

        self.queue_processing_latency_seconds = Histogram(
            "queue_processing_latency_seconds",
            "End-to-end queue item processing latency",
            labelnames=["queue_name"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 60.0),
        )

        # ============ CACHE METRICS ============
        self.cache_hits_total = Counter(
            "cache_hits_total", "Total cache hits", labelnames=["cache_name"]
        )

        self.cache_misses_total = Counter(
            "cache_misses_total", "Total cache misses", labelnames=["cache_name"]
        )

        self.cache_hit_ratio = Gauge(
            "cache_hit_ratio",
            "Cache hit ratio (hits / (hits + misses))",
            labelnames=["cache_name"],
        )

        # ============ WEBSOCKET METRICS ============
        self.websocket_connections_active = Gauge(
            "websocket_connections_active",
            "Current number of active WebSocket connections",
        )

        self.websocket_connections_total = Counter(
            "websocket_connections_total", "Total WebSocket connections (cumulative)"
        )

        self.websocket_messages_sent_total = Counter(
            "websocket_messages_sent_total", "Total WebSocket messages sent"
        )

        self.websocket_messages_received_total = Counter(
            "websocket_messages_received_total", "Total WebSocket messages received"
        )

        self.websocket_connection_duration_seconds = Histogram(
            "websocket_connection_duration_seconds",
            "WebSocket connection lifetime in seconds",
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 3600.0),
        )

        # ============ PROCESS METRICS ============
        self.process_memory_usage_bytes = Gauge(
            "process_memory_usage_bytes", "Process RSS memory usage in bytes"
        )

        # ============ HTTP REQUEST METRICS ============
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds",
            labelnames=["method", "endpoint", "status"],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
        )

        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            labelnames=["method", "endpoint", "status"],
        )

    @contextmanager
    def time_query(self, query_type: str = "unknown"):
        """
        Context manager to time database queries.

        Args:
            query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)

        Example:
            with metrics.time_query('SELECT'):
                result = db.execute(query)
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.db_query_duration_seconds.labels(query_type=query_type).observe(
                duration
            )

    @contextmanager
    def time_connection_wait(self):
        """
        Context manager to measure connection pool wait time.

        Example:
            with metrics.time_connection_wait():
                conn = pool.get_connection()
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.db_connection_wait_seconds.observe(duration)

    @contextmanager
    def time_queue_processing(self, queue_name: str):
        """
        Context manager to measure queue processing latency.

        Args:
            queue_name: Name of the queue being processed

        Example:
            with metrics.time_queue_processing('task_queue'):
                process_task(item)
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.queue_processing_latency_seconds.labels(queue_name=queue_name).observe(
                duration
            )

    @contextmanager
    def time_websocket_connection(self):
        """
        Context manager to measure WebSocket connection lifetime.

        Example:
            with metrics.time_websocket_connection():
                # WebSocket is active
                pass
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.websocket_connection_duration_seconds.observe(duration)

    def record_cache_hit(self, cache_name: str) -> None:
        """
        Record a cache hit and update hit ratio.

        Args:
            cache_name: Name of the cache
        """
        self.cache_hits_total.labels(cache_name=cache_name).inc()
        self._update_cache_hit_ratio(cache_name)

    def record_cache_miss(self, cache_name: str) -> None:
        """
        Record a cache miss and update hit ratio.

        Args:
            cache_name: Name of the cache
        """
        self.cache_misses_total.labels(cache_name=cache_name).inc()
        self._update_cache_hit_ratio(cache_name)

    def _update_cache_hit_ratio(self, cache_name: str) -> None:
        """Update cache hit ratio for a given cache."""
        try:
            # Note: In Prometheus client, we can't easily read metric values
            # This is a simplified approach; in production, calculate elsewhere
            hits = self.cache_hits_total.labels(cache_name=cache_name)._value.get()
            misses = self.cache_misses_total.labels(cache_name=cache_name)._value.get()
            total = hits + misses
            if total > 0:
                ratio = hits / total
                self.cache_hit_ratio.labels(cache_name=cache_name).set(ratio)
        except Exception as e:
            logger.debug(f"Could not update cache hit ratio for {cache_name}: {e}")

    def record_queue_depth(self, queue_name: str, depth: int) -> None:
        """
        Update queue depth gauge.

        Args:
            queue_name: Name of the queue
            depth: Current number of items in queue
        """
        self.queue_depth.labels(queue_name=queue_name).set(depth)

    def increment_queue_processed(self, queue_name: str) -> None:
        """
        Increment processed items counter for a queue.

        Args:
            queue_name: Name of the queue
        """
        self.queue_processed_total.labels(queue_name=queue_name).inc()

    def record_connection_active(self, count: int) -> None:
        """
        Update active connection count.

        Args:
            count: Current number of active connections
        """
        self.db_connections_active.set(count)

    def increment_connection_created(self) -> None:
        """Record creation of a new connection."""
        self.db_connections_total.inc()

    def increment_connection_reused(self) -> None:
        """Record reuse of an existing connection."""
        self.db_connections_reused.inc()

    def record_websocket_connection_opened(self) -> None:
        """Record a new WebSocket connection."""
        self.websocket_connections_active.inc()
        self.websocket_connections_total.inc()

    def record_websocket_connection_closed(self) -> None:
        """Record closure of a WebSocket connection."""
        self.websocket_connections_active.dec()

    def increment_websocket_message_sent(self) -> None:
        """Record a WebSocket message sent."""
        self.websocket_messages_sent_total.inc()

    def increment_websocket_message_received(self) -> None:
        """Record a WebSocket message received."""
        self.websocket_messages_received_total.inc()

    def record_process_memory(self, memory_bytes: int) -> None:
        """
        Update process memory usage gauge.

        Args:
            memory_bytes: Current RSS memory in bytes
        """
        self.process_memory_usage_bytes.set(memory_bytes)

    def record_http_request(
        self, method: str, endpoint: str, status: int, duration: float
    ) -> None:
        """
        Record an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Request path
            status: HTTP status code
            duration: Request duration in seconds
        """
        self.http_request_duration_seconds.labels(
            method=method, endpoint=endpoint, status=status
        ).observe(duration)
        self.http_requests_total.labels(
            method=method, endpoint=endpoint, status=status
        ).inc()


# Global metrics instance
_metrics_registry: Optional[MetricsRegistry] = None


def get_metrics() -> MetricsRegistry:
    """Get or create the global metrics registry."""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


def initialize_metrics() -> MetricsRegistry:
    """Initialize metrics registry. Called at application startup."""
    global _metrics_registry
    _metrics_registry = MetricsRegistry()
    logger.info("Metrics registry initialized")
    return _metrics_registry
