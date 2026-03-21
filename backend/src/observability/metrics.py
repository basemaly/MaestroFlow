"""
Prometheus metrics collection module for MaestroFlow.

Provides metrics for:
- Connection pool usage and efficiency
- Database query performance
- Queue depths and processing latency
- Cache hit/miss ratios
- WebSocket connection stability
- Memory usage trends
- HTTP request/response times
"""

import threading
from contextlib import contextmanager
from time import time
from typing import Generator

from prometheus_client import Counter, Gauge, Histogram, Summary


# ============================================================================
# Connection Pool Metrics
# ============================================================================

db_connections_active = Gauge(
    "db_connections_active",
    "Current number of active connections in the pool",
    labelnames=["pool_name"],
)

db_connections_total = Counter(
    "db_connections_total",
    "Total number of connections created",
    labelnames=["pool_name"],
)

db_connections_reused = Counter(
    "db_connections_reused",
    "Total number of times a connection was reused from pool",
    labelnames=["pool_name"],
)

db_connection_wait_seconds = Histogram(
    "db_connection_wait_seconds",
    "Time spent waiting for a database connection",
    labelnames=["pool_name"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

# ============================================================================
# Database Query Metrics
# ============================================================================

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query execution time",
    labelnames=["query_type"],  # SELECT, INSERT, UPDATE, DELETE
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

db_query_count = Counter(
    "db_queries_total",
    "Total number of database queries executed",
    labelnames=["query_type"],
)

db_slow_queries = Counter(
    "db_slow_queries_total",
    "Number of slow queries (> 100ms)",
    labelnames=["query_type"],
)

# ============================================================================
# Queue Metrics
# ============================================================================

queue_depth = Gauge(
    "queue_depth",
    "Current number of items in the queue",
    labelnames=["queue_name"],
)

queue_processed_total = Counter(
    "queue_processed_total",
    "Total number of items processed from the queue",
    labelnames=["queue_name"],
)

queue_processing_latency_seconds = Histogram(
    "queue_processing_latency_seconds",
    "End-to-end latency for queue item processing",
    labelnames=["queue_name"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
)

queue_errors_total = Counter(
    "queue_errors_total",
    "Total number of errors during queue processing",
    labelnames=["queue_name", "error_type"],
)

# ============================================================================
# Cache Metrics
# ============================================================================

cache_hits_total = Counter(
    "cache_hits_total",
    "Total number of cache hits",
    labelnames=["cache_name"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total number of cache misses",
    labelnames=["cache_name"],
)

cache_hit_ratio = Gauge(
    "cache_hit_ratio",
    "Cache hit ratio (0-1)",
    labelnames=["cache_name"],
)

cache_evictions_total = Counter(
    "cache_evictions_total",
    "Total number of cache evictions",
    labelnames=["cache_name", "reason"],  # reason: ttl, lru, manual, etc.
)

# ============================================================================
# WebSocket Metrics
# ============================================================================

websocket_connections_active = Gauge(
    "websocket_connections_active",
    "Current number of active WebSocket connections",
    labelnames=["endpoint"],
)

websocket_connections_total = Counter(
    "websocket_connections_total",
    "Total number of WebSocket connections (cumulative)",
    labelnames=["endpoint"],
)

websocket_messages_sent_total = Counter(
    "websocket_messages_sent_total",
    "Total number of WebSocket messages sent",
    labelnames=["endpoint"],
)

websocket_messages_received_total = Counter(
    "websocket_messages_received_total",
    "Total number of WebSocket messages received",
    labelnames=["endpoint"],
)

websocket_connection_duration_seconds = Histogram(
    "websocket_connection_duration_seconds",
    "WebSocket connection lifetime duration",
    labelnames=["endpoint"],
    buckets=(1, 5, 10, 30, 60, 300, 3600),
)

websocket_heartbeat_failures_total = Counter(
    "websocket_heartbeat_failures_total",
    "Total number of WebSocket heartbeat failures",
    labelnames=["endpoint"],
)

# ============================================================================
# HTTP Request Metrics
# ============================================================================

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "endpoint", "status"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    labelnames=["method", "endpoint", "status"],
)

http_request_size_bytes = Summary(
    "http_request_size_bytes",
    "HTTP request body size in bytes",
    labelnames=["method", "endpoint"],
)

http_response_size_bytes = Summary(
    "http_response_size_bytes",
    "HTTP response body size in bytes",
    labelnames=["method", "endpoint", "status"],
)

# ============================================================================
# Memory & System Metrics
# ============================================================================

process_memory_rss_bytes = Gauge(
    "process_memory_rss_bytes",
    "Process Resident Set Size (RSS) in bytes",
)

process_memory_vms_bytes = Gauge(
    "process_memory_vms_bytes",
    "Process Virtual Memory Size (VMS) in bytes",
)

process_memory_percent = Gauge(
    "process_memory_percent",
    "Process memory as a percentage of total system memory",
)

process_page_faults_total = Counter(
    "process_page_faults_total",
    "Total number of page faults",
    labelnames=["fault_type"],  # major, minor
)

process_memory_growth_rate_mb_per_minute = Gauge(
    "process_memory_growth_rate_mb_per_minute",
    "Memory growth rate in MB per minute (negative indicates shrinkage)",
)

# ============================================================================
# Exception Metrics
# ============================================================================

exceptions_total = Counter(
    "exceptions_total",
    "Total number of unhandled exceptions",
    labelnames=["exception_type"],
)

# ============================================================================
# Health & Composite Metrics
# ============================================================================

health_check_timestamp = Gauge(
    "health_check_timestamp",
    "Timestamp of last health check",
)

system_health_score = Gauge(
    "system_health_score",
    "Overall system health score (0-100)",
)

component_health_score = Gauge(
    "component_health_score",
    "Component-specific health score (0-100)",
    labelnames=["component"],
)


# ============================================================================
# Helper Functions & Context Managers
# ============================================================================

_metrics_lock = threading.Lock()


@contextmanager
def measure_db_query_time(query_type: str = "SELECT") -> Generator[None, None, None]:
    """
    Context manager to measure database query execution time.

    Args:
        query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)

    Usage:
        with measure_db_query_time("SELECT"):
            cursor.execute("SELECT * FROM table")
    """
    start_time = time()
    try:
        yield
        duration = time() - start_time
        with _metrics_lock:
            db_query_duration_seconds.labels(query_type=query_type).observe(duration)
            db_query_count.labels(query_type=query_type).inc()
            if duration > 0.1:  # 100ms threshold
                db_slow_queries.labels(query_type=query_type).inc()
    except Exception:
        raise


@contextmanager
def measure_connection_wait_time(pool_name: str = "default") -> Generator[None, None, None]:
    """
    Context manager to measure time spent waiting for a database connection.

    Args:
        pool_name: Name of the connection pool

    Usage:
        with measure_connection_wait_time("executive"):
            conn = pool.get_connection()
    """
    start_time = time()
    try:
        yield
        duration = time() - start_time
        with _metrics_lock:
            db_connection_wait_seconds.labels(pool_name=pool_name).observe(duration)
    except Exception:
        raise


@contextmanager
def measure_queue_processing_time(queue_name: str) -> Generator[None, None, None]:
    """
    Context manager to measure queue item processing latency.

    Args:
        queue_name: Name of the queue

    Usage:
        with measure_queue_processing_time("approvals"):
            process_queue_item(item)
    """
    start_time = time()
    try:
        yield
        duration = time() - start_time
        with _metrics_lock:
            queue_processing_latency_seconds.labels(queue_name=queue_name).observe(duration)
            queue_processed_total.labels(queue_name=queue_name).inc()
    except Exception:
        queue_errors_total.labels(queue_name=queue_name, error_type="unknown").inc()
        raise


@contextmanager
def measure_http_request(method: str, endpoint: str) -> Generator[None, None, None]:
    """
    Context manager to measure HTTP request duration.

    Note: This should be called from middleware; returns (start_time, duration)
    For use in middleware:
        start = time()
        try:
            response = await call_next(request)
            duration = time() - start
            status = response.status_code
        except:
            status = 500
            duration = time() - start
            raise
        finally:
            http_request_duration_seconds.labels(...).observe(duration)

    Args:
        method: HTTP method (GET, POST, etc.)
        endpoint: Endpoint path

    Usage:
        with measure_http_request("GET", "/approvals"):
            response = await handler()
    """
    start_time = time()
    status = None
    try:
        yield
        status = 200  # Default to success if not set
    except Exception:
        status = 500
        raise
    finally:
        duration = time() - start_time
        if status:
            with _metrics_lock:
                http_request_duration_seconds.labels(method=method, endpoint=endpoint, status=status).observe(duration)
                http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()


def record_cache_operation(cache_name: str, hit: bool, is_eviction: bool = False, reason: str | None = None) -> None:
    """
    Record a cache hit or miss.

    Args:
        cache_name: Name of the cache
        hit: True if cache hit, False if miss
        is_eviction: True if this operation resulted in an eviction
        reason: Reason for eviction (if is_eviction=True): 'ttl', 'lru', 'manual', etc.

    Usage:
        record_cache_operation("approvals_cache", hit=True)
        record_cache_operation("user_cache", hit=False, is_eviction=True, reason="lru")
    """
    with _metrics_lock:
        if hit:
            cache_hits_total.labels(cache_name=cache_name).inc()
        else:
            cache_misses_total.labels(cache_name=cache_name).inc()

        if is_eviction and reason:
            cache_evictions_total.labels(cache_name=cache_name, reason=reason).inc()

        # Calculate and update hit ratio
        hits = cache_hits_total.labels(cache_name=cache_name)._value.get()
        misses = cache_misses_total.labels(cache_name=cache_name)._value.get()
        total = hits + misses
        if total > 0:
            ratio = hits / total
            cache_hit_ratio.labels(cache_name=cache_name).set(ratio)


def record_exception(exception_type: str) -> None:
    """
    Record an unhandled exception.

    Args:
        exception_type: Type of exception (e.g., 'ValueError', 'ConnectionError')

    Usage:
        try:
            ...
        except Exception as e:
            record_exception(type(e).__name__)
            raise
    """
    with _metrics_lock:
        exceptions_total.labels(exception_type=exception_type).inc()


def set_pool_metrics(
    pool_name: str,
    active_count: int,
    total_created: int,
    total_reused: int,
) -> None:
    """
    Update connection pool metrics.

    Args:
        pool_name: Name of the connection pool
        active_count: Current number of active connections
        total_created: Total connections created (since startup)
        total_reused: Total connections reused from pool

    Usage:
        set_pool_metrics("executive", active_count=5, total_created=100, total_reused=950)
    """
    with _metrics_lock:
        db_connections_active.labels(pool_name=pool_name).set(active_count)
        db_connections_total.labels(pool_name=pool_name)._value.set(total_created)
        db_connections_reused.labels(pool_name=pool_name)._value.set(total_reused)


def set_queue_depth(queue_name: str, depth: int) -> None:
    """
    Update queue depth metric.

    Args:
        queue_name: Name of the queue
        depth: Current number of items in the queue

    Usage:
        set_queue_depth("approvals", depth=42)
    """
    with _metrics_lock:
        queue_depth.labels(queue_name=queue_name).set(depth)


def set_memory_metrics(
    rss_bytes: int,
    vms_bytes: int,
    percent: float,
    growth_rate_mb_per_minute: float = 0.0,
) -> None:
    """
    Update memory usage metrics.

    Args:
        rss_bytes: Resident Set Size in bytes
        vms_bytes: Virtual Memory Size in bytes
        percent: Memory as percentage of total system memory
        growth_rate_mb_per_minute: Growth rate in MB/minute (negative = shrinking)

    Usage:
        set_memory_metrics(rss_bytes=512000000, vms_bytes=1024000000, percent=25.5, growth_rate_mb_per_minute=0.5)
    """
    with _metrics_lock:
        process_memory_rss_bytes.set(rss_bytes)
        process_memory_vms_bytes.set(vms_bytes)
        process_memory_percent.set(percent)
        process_memory_growth_rate_mb_per_minute.set(growth_rate_mb_per_minute)


def set_health_score(overall_score: float, component_scores: dict[str, float] | None = None) -> None:
    """
    Update health score metrics.

    Args:
        overall_score: Overall system health score (0-100)
        component_scores: Dict of component_name -> score (0-100)

    Usage:
        set_health_score(
            overall_score=85,
            component_scores={
                "database": 90,
                "queue": 80,
                "cache": 85,
                "memory": 80,
                "websockets": 85,
            }
        )
    """
    with _metrics_lock:
        system_health_score.set(overall_score)
        if component_scores:
            for component, score in component_scores.items():
                component_health_score.labels(component=component).set(score)
        health_check_timestamp.set_to_current_time()


# ============================================================================
# Circuit Breaker Metric Functions
# ============================================================================


def record_circuit_breaker_state_change(service: str, from_state: str, to_state: str) -> None:
    """
    Record a circuit breaker state change.

    Args:
        service: Service name
        from_state: Previous state (CLOSED, OPEN, HALF_OPEN)
        to_state: New state (CLOSED, OPEN, HALF_OPEN)

    Usage:
        record_circuit_breaker_state_change("surfsense", "CLOSED", "OPEN")
    """
    with _metrics_lock:
        circuit_breaker_state_changes_total.labels(service=service, from_state=from_state, to_state=to_state).inc()
        # Map state to numeric value
        state_map = {"CLOSED": 0, "OPEN": 1, "HALF_OPEN": 2}
        circuit_breaker_state.labels(service=service).set(state_map.get(to_state, 0))


def record_circuit_breaker_failure(service: str) -> None:
    """
    Record a failure in circuit breaker.

    Args:
        service: Service name

    Usage:
        record_circuit_breaker_failure("litellm")
    """
    with _metrics_lock:
        circuit_breaker_failures_total.labels(service=service).inc()


def record_circuit_breaker_success(service: str) -> None:
    """
    Record a success in circuit breaker.

    Args:
        service: Service name

    Usage:
        record_circuit_breaker_success("langfuse")
    """
    with _metrics_lock:
        circuit_breaker_successes_total.labels(service=service).inc()


def record_circuit_breaker_open_duration(service: str, duration_seconds: float) -> None:
    """
    Record the duration circuit breaker was in OPEN state.

    Args:
        service: Service name
        duration_seconds: Duration in seconds

    Usage:
        record_circuit_breaker_open_duration("surfsense", 45.5)
    """
    with _metrics_lock:
        circuit_breaker_open_duration_seconds.labels(service=service).observe(duration_seconds)


def record_circuit_breaker_half_open_attempt(service: str) -> None:
    """
    Record a half-open state attempt.

    Args:
        service: Service name

    Usage:
        record_circuit_breaker_half_open_attempt("openvking")
    """
    with _metrics_lock:
        circuit_breaker_half_open_attempts_total.labels(service=service).inc()


# ============================================================================
# HTTP Client Manager Metric Functions
# ============================================================================


def set_http_client_pool_metrics(
    service: str,
    active_connections: int,
    total_capacity: int,
) -> None:
    """
    Update HTTP client pool metrics.

    Args:
        service: Service name
        active_connections: Current active connections
        total_capacity: Total pool capacity

    Usage:
        set_http_client_pool_metrics("surfsense", active_connections=3, total_capacity=10)
    """
    with _metrics_lock:
        http_client_pool_connections_active.labels(service=service).set(active_connections)
        http_client_pool_connections_total.labels(service=service).set(total_capacity)
        if total_capacity > 0:
            utilization = active_connections / total_capacity
            http_client_pool_utilization.labels(service=service).set(utilization)


def record_http_client_request(
    service: str,
    status: str,
    duration_seconds: float,
) -> None:
    """
    Record an HTTP client request via circuit breaker.

    Args:
        service: Service name
        status: Request status (success, failure, timeout, open)
        duration_seconds: Request duration in seconds

    Usage:
        record_http_client_request("litellm", "success", 0.45)
    """
    with _metrics_lock:
        http_client_request_duration_seconds.labels(service=service, status=status).observe(duration_seconds)
        http_client_requests_total.labels(service=service, status=status).inc()


def record_http_client_retry(service: str) -> None:
    """
    Record an HTTP client retry attempt.

    Args:
        service: Service name

    Usage:
        record_http_client_retry("langfuse")
    """
    with _metrics_lock:
        http_client_retries_total.labels(service=service).inc()


# ============================================================================
# Subagent Pool Metric Functions
# ============================================================================


def set_subagent_pool_metrics(
    pool_size: int,
    active_workers: int,
    pending_tasks: int,
    queue_depth: int,
    cpu_utilization: float,
    memory_utilization: float,
    health_score: float,
) -> None:
    """
    Update subagent pool metrics.

    Args:
        pool_size: Current pool size
        active_workers: Current active workers
        pending_tasks: Pending tasks count
        queue_depth: Queue depth
        cpu_utilization: CPU utilization (0-100)
        memory_utilization: Memory utilization (0-100)
        health_score: Overall health score (0-100)

    Usage:
        set_subagent_pool_metrics(
            pool_size=8,
            active_workers=5,
            pending_tasks=12,
            queue_depth=2,
            cpu_utilization=45.5,
            memory_utilization=62.3,
            health_score=85.0,
        )
    """
    with _metrics_lock:
        subagent_pool_size.set(pool_size)
        subagent_pool_active_workers.set(active_workers)
        subagent_pool_pending_tasks.set(pending_tasks)
        subagent_pool_queue_depth.set(queue_depth)
        subagent_pool_cpu_utilization.set(cpu_utilization)
        subagent_pool_memory_utilization.set(memory_utilization)
        subagent_pool_health_score.set(health_score)


def record_subagent_task(
    status: str,
    duration_seconds: float,
) -> None:
    """
    Record a subagent task execution.

    Args:
        status: Task status (success, failure, timeout, cancelled)
        duration_seconds: Task duration in seconds

    Usage:
        record_subagent_task("success", 2.45)
    """
    with _metrics_lock:
        subagent_task_duration_seconds.labels(status=status).observe(duration_seconds)
        subagent_tasks_total.labels(status=status).inc()


def record_subagent_pool_size_adjustment(direction: str) -> None:
    """
    Record a subagent pool size adjustment.

    Args:
        direction: Adjustment direction (up, down, stable)

    Usage:
        record_subagent_pool_size_adjustment("up")
    """
    with _metrics_lock:
        subagent_pool_size_adjustments_total.labels(direction=direction).inc()


# ============================================================================
# Connection Pool Health Metric Functions
# ============================================================================


def set_httpx_connection_pool_metrics(
    pool_id: str,
    idle_connections: int,
    busy_connections: int,
) -> None:
    """
    Update httpx connection pool metrics.

    Args:
        pool_id: Pool identifier
        idle_connections: Number of idle connections
        busy_connections: Number of busy connections

    Usage:
        set_httpx_connection_pool_metrics("surfsense_pool", idle_connections=5, busy_connections=2)
    """
    with _metrics_lock:
        httpx_connection_pool_connections.labels(pool_id=pool_id, status="idle").set(idle_connections)
        httpx_connection_pool_connections.labels(pool_id=pool_id, status="busy").set(busy_connections)


def record_httpx_connection_pool_timeout(pool_id: str) -> None:
    """
    Record a connection pool timeout.

    Args:
        pool_id: Pool identifier

    Usage:
        record_httpx_connection_pool_timeout("surfsense_pool")
    """
    with _metrics_lock:
        httpx_connection_pool_timeouts_total.labels(pool_id=pool_id).inc()


# ============================================================================
# LLM Operations Metrics
# ============================================================================

llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Total cost of LLM API calls in USD",
    labelnames=["model"],
)

llm_token_usage = Histogram(
    "llm_token_usage",
    "Token usage per LLM call",
    labelnames=["token_type"],  # input, output, total
    buckets=(10, 50, 100, 500, 1000, 5000, 10000),
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM API call latency",
    labelnames=["model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

llm_calls_total = Counter(
    "llm_calls_total",
    "Total number of LLM API calls",
    labelnames=["model", "status"],  # status: success, error, timeout
)

# ============================================================================
# Circuit Breaker Metrics
# ============================================================================

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)",
    labelnames=["service"],
)

circuit_breaker_state_changes_total = Counter(
    "circuit_breaker_state_changes_total",
    "Total number of circuit breaker state changes",
    labelnames=["service", "from_state", "to_state"],
)

circuit_breaker_failures_total = Counter(
    "circuit_breaker_failures_total",
    "Total number of failures recorded by circuit breaker",
    labelnames=["service"],
)

circuit_breaker_successes_total = Counter(
    "circuit_breaker_successes_total",
    "Total number of successes recorded by circuit breaker",
    labelnames=["service"],
)

circuit_breaker_open_duration_seconds = Histogram(
    "circuit_breaker_open_duration_seconds",
    "Duration circuit breaker spent in OPEN state",
    labelnames=["service"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
)

circuit_breaker_half_open_attempts_total = Counter(
    "circuit_breaker_half_open_attempts_total",
    "Total number of attempts during HALF_OPEN state",
    labelnames=["service"],
)

# ============================================================================
# HTTP Client Manager Metrics
# ============================================================================

http_client_pool_connections_active = Gauge(
    "http_client_pool_connections_active",
    "Current number of active connections in HTTP client pool",
    labelnames=["service"],
)

http_client_pool_connections_total = Gauge(
    "http_client_pool_connections_total",
    "Total capacity of HTTP client pool",
    labelnames=["service"],
)

http_client_pool_utilization = Gauge(
    "http_client_pool_utilization",
    "HTTP client pool utilization (0-1)",
    labelnames=["service"],
)

http_client_request_duration_seconds = Histogram(
    "http_client_request_duration_seconds",
    "HTTP client request duration via circuit breaker",
    labelnames=["service", "status"],  # status: success, failure, timeout, open
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
)

http_client_requests_total = Counter(
    "http_client_requests_total",
    "Total number of HTTP requests via circuit breaker",
    labelnames=["service", "status"],
)

http_client_retries_total = Counter(
    "http_client_retries_total",
    "Total number of retry attempts",
    labelnames=["service"],
)

# ============================================================================
# Subagent Pool Metrics
# ============================================================================

subagent_pool_size = Gauge(
    "subagent_pool_size",
    "Current size of subagent worker pool",
)

subagent_pool_active_workers = Gauge(
    "subagent_pool_active_workers",
    "Current number of active subagent workers",
)

subagent_pool_pending_tasks = Gauge(
    "subagent_pool_pending_tasks",
    "Current number of pending subagent tasks in queue",
)

subagent_pool_queue_depth = Gauge(
    "subagent_pool_queue_depth",
    "Current depth of subagent task queue",
)

subagent_task_duration_seconds = Histogram(
    "subagent_task_duration_seconds",
    "Subagent task execution duration",
    labelnames=["status"],  # success, failure, timeout, cancelled
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)

subagent_tasks_total = Counter(
    "subagent_tasks_total",
    "Total number of subagent tasks executed",
    labelnames=["status"],
)

subagent_pool_size_adjustments_total = Counter(
    "subagent_pool_size_adjustments_total",
    "Total number of pool size adjustments",
    labelnames=["direction"],  # up, down, stable
)

subagent_pool_cpu_utilization = Gauge(
    "subagent_pool_cpu_utilization",
    "System CPU utilization monitored by pool",
)

subagent_pool_memory_utilization = Gauge(
    "subagent_pool_memory_utilization",
    "System memory utilization monitored by pool",
)

subagent_pool_health_score = Gauge(
    "subagent_pool_health_score",
    "Overall health score of subagent pool (0-100)",
)

# ============================================================================
# Connection Pool Health Metrics (httpx)
# ============================================================================

httpx_connection_pool_connections = Gauge(
    "httpx_connection_pool_connections",
    "Number of connections in httpx connection pool",
    labelnames=["pool_id", "status"],  # status: idle, busy
)

httpx_connection_pool_timeouts_total = Counter(
    "httpx_connection_pool_timeouts_total",
    "Total number of connection pool timeout errors",
    labelnames=["pool_id"],
)
