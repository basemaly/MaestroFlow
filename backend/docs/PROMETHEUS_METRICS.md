---
type: reference
title: Prometheus Metrics Reference
created: 2026-03-21
tags:
  - prometheus
  - monitoring
  - circuit-breaker
  - subagent-pool
  - http-client
related:
  - '[[MAESTROFLOW-RESILIENCE-01]]'
---

# Prometheus Metrics Reference

This document describes all Prometheus metrics exposed by MaestroFlow for monitoring circuit breakers, HTTP client connections, and subagent pool health.

## Circuit Breaker Metrics

Metrics for tracking the health and behavior of circuit breakers protecting external service calls.

### `circuit_breaker_state`
- **Type**: Gauge
- **Labels**: `service` (service name)
- **Values**: 0 (CLOSED), 1 (OPEN), 2 (HALF_OPEN)
- **Description**: Current state of the circuit breaker for a service
- **Example**: `circuit_breaker_state{service="surfsense"} 0`

### `circuit_breaker_state_changes_total`
- **Type**: Counter
- **Labels**: `service`, `from_state`, `to_state`
- **Description**: Total number of circuit breaker state transitions
- **Example**: `circuit_breaker_state_changes_total{service="litellm",from_state="CLOSED",to_state="OPEN"} 3`

### `circuit_breaker_failures_total`
- **Type**: Counter
- **Labels**: `service`
- **Description**: Total number of failures recorded by the circuit breaker
- **Example**: `circuit_breaker_failures_total{service="surfsense"} 15`

### `circuit_breaker_successes_total`
- **Type**: Counter
- **Labels**: `service`
- **Description**: Total number of successful requests recorded by the circuit breaker
- **Example**: `circuit_breaker_successes_total{service="litellm"} 2450`

### `circuit_breaker_open_duration_seconds`
- **Type**: Histogram
- **Labels**: `service`
- **Buckets**: 1, 5, 10, 30, 60, 120, 300, 600 seconds
- **Description**: Duration the circuit breaker spent in OPEN state
- **Example**: `circuit_breaker_open_duration_seconds_bucket{service="langfuse",le="60"} 2`

### `circuit_breaker_half_open_attempts_total`
- **Type**: Counter
- **Labels**: `service`
- **Description**: Total number of attempts made during HALF_OPEN state
- **Example**: `circuit_breaker_half_open_attempts_total{service="openvking"} 12`

## HTTP Client Manager Metrics

Metrics for tracking HTTP client connection pool usage and request performance through the circuit breaker.

### `http_client_pool_connections_active`
- **Type**: Gauge
- **Labels**: `service`
- **Description**: Current number of active connections in the HTTP client pool
- **Example**: `http_client_pool_connections_active{service="surfsense"} 3`

### `http_client_pool_connections_total`
- **Type**: Gauge
- **Labels**: `service`
- **Description**: Total capacity of the HTTP client connection pool
- **Example**: `http_client_pool_connections_total{service="litellm"} 100`

### `http_client_pool_utilization`
- **Type**: Gauge
- **Labels**: `service`
- **Range**: 0-1
- **Description**: HTTP client pool utilization ratio (active / total)
- **Example**: `http_client_pool_utilization{service="langfuse"} 0.15`

### `http_client_request_duration_seconds`
- **Type**: Histogram
- **Labels**: `service`, `status` (success, failure, timeout, open)
- **Buckets**: 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0 seconds
- **Description**: HTTP client request duration through circuit breaker
- **Example**: `http_client_request_duration_seconds_bucket{service="surfsense",status="success",le="1.0"} 450`

### `http_client_requests_total`
- **Type**: Counter
- **Labels**: `service`, `status`
- **Description**: Total number of HTTP requests via circuit breaker
- **Example**: `http_client_requests_total{service="litellm",status="success"} 2450`

### `http_client_retries_total`
- **Type**: Counter
- **Labels**: `service`
- **Description**: Total number of retry attempts made by circuit breaker
- **Example**: `http_client_retries_total{service="langfuse"} 5`

## Subagent Pool Metrics

Metrics for monitoring the dynamic subagent worker pool, including sizing, utilization, and task execution.

### `subagent_pool_size`
- **Type**: Gauge
- **Description**: Current size of the subagent worker pool
- **Range**: 2-16 workers
- **Example**: `subagent_pool_size 8`

### `subagent_pool_active_workers`
- **Type**: Gauge
- **Description**: Current number of active subagent workers
- **Example**: `subagent_pool_active_workers 5`

### `subagent_pool_pending_tasks`
- **Type**: Gauge
- **Description**: Current number of pending subagent tasks in queue
- **Example**: `subagent_pool_pending_tasks 12`

### `subagent_pool_queue_depth`
- **Type**: Gauge
- **Description**: Current depth of subagent task queue
- **Example**: `subagent_pool_queue_depth 12`

### `subagent_task_duration_seconds`
- **Type**: Histogram
- **Labels**: `status` (success, failure, timeout, cancelled)
- **Buckets**: 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0 seconds
- **Description**: Subagent task execution duration
- **Example**: `subagent_task_duration_seconds_bucket{status="success",le="10.0"} 1245`

### `subagent_tasks_total`
- **Type**: Counter
- **Labels**: `status`
- **Description**: Total number of subagent tasks executed
- **Example**: `subagent_tasks_total{status="success"} 1250`

### `subagent_pool_size_adjustments_total`
- **Type**: Counter
- **Labels**: `direction` (up, down, stable)
- **Description**: Total number of pool size adjustments
- **Example**: `subagent_pool_size_adjustments_total{direction="up"} 3`

### `subagent_pool_cpu_utilization`
- **Type**: Gauge
- **Range**: 0-100
- **Description**: System CPU utilization monitored by the pool adjustment algorithm
- **Example**: `subagent_pool_cpu_utilization 45.5`

### `subagent_pool_memory_utilization`
- **Type**: Gauge
- **Range**: 0-100
- **Description**: System memory utilization monitored by the pool adjustment algorithm
- **Example**: `subagent_pool_memory_utilization 62.3`

### `subagent_pool_health_score`
- **Type**: Gauge
- **Range**: 0-100
- **Description**: Overall health score of the subagent pool
- **Calculation**: Starts at 100, reduced by CPU/memory pressure and queue depth
- **Example**: `subagent_pool_health_score 85.0`

## Connection Pool Health Metrics

Metrics for tracking httpx connection pool status.

### `httpx_connection_pool_connections`
- **Type**: Gauge
- **Labels**: `pool_id`, `status` (idle, busy)
- **Description**: Number of connections in httpx connection pool
- **Example**: `httpx_connection_pool_connections{pool_id="surfsense_pool",status="idle"} 5`

### `httpx_connection_pool_timeouts_total`
- **Type**: Counter
- **Labels**: `pool_id`
- **Description**: Total number of connection pool timeout errors
- **Example**: `httpx_connection_pool_timeouts_total{pool_id="litellm_pool"} 2`

## Monitoring Recommendations

### Alerting Rules

```yaml
groups:
  - name: maestroflow_resilience
    rules:
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{service!=""} == 1
        for: 5m
        annotations:
          summary: "Circuit breaker open for {{ $labels.service }}"

      - alert: HighFailureRate
        expr: |
          rate(circuit_breaker_failures_total[5m]) > 0.1
        annotations:
          summary: "High failure rate for {{ $labels.service }}"

      - alert: SubagentPoolHealthLow
        expr: subagent_pool_health_score < 50
        annotations:
          summary: "Subagent pool health degraded: {{ $value }}"

      - alert: SubagentQueueBacklog
        expr: subagent_pool_queue_depth > (subagent_pool_size * 2)
        for: 2m
        annotations:
          summary: "Subagent queue backlog increasing"

      - alert: HighSystemResourceUsage
        expr: |
          subagent_pool_cpu_utilization > 90 or
          subagent_pool_memory_utilization > 95
        annotations:
          summary: "System resources critical"
```

### Useful Queries

**Failure rate for a service (5-minute window):**
```promql
rate(circuit_breaker_failures_total{service="surfsense"}[5m])
```

**Success rate for a service:**
```promql
rate(circuit_breaker_successes_total{service="litellm"}[5m]) /
(rate(circuit_breaker_successes_total{service="litellm"}[5m]) +
 rate(circuit_breaker_failures_total{service="litellm"}[5m]))
```

**Average HTTP request latency:**
```promql
histogram_quantile(0.95,
  rate(http_client_request_duration_seconds_bucket{service="surfsense",status="success"}[5m])
)
```

**Pool saturation:**
```promql
subagent_pool_active_workers / subagent_pool_size
```

**Task success rate:**
```promql
rate(subagent_tasks_total{status="success"}[5m]) /
rate(subagent_tasks_total[5m])
```

## Metric Collection Endpoints

All metrics are exposed via Prometheus `/metrics` endpoint at:
```
GET /metrics
```

The endpoint is typically available at:
- Development: `http://localhost:8000/metrics`
- Production: `https://api.maestroflow.com/metrics`
