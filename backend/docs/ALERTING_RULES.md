---
type: reference
title: MaestroFlow Alerting Rules
created: 2026-03-21
tags:
  - alerting
  - prometheus
  - monitoring
  - resilience
related:
  - '[[PROMETHEUS_METRICS]]'
---

# MaestroFlow Alerting Rules

This document defines alerting thresholds and rules for the MaestroFlow resilience system.

## Rule Groups

### Circuit Breaker Alerts

#### CircuitBreakerOpen
Alert when a circuit breaker transitions to OPEN state.

```yaml
- alert: CircuitBreakerOpen
  expr: circuit_breaker_state{service!=""} == 1
  for: 1m
  labels:
    severity: warning
    component: circuit-breaker
  annotations:
    summary: "Circuit breaker OPEN for {{ $labels.service }}"
    description: "Service {{ $labels.service }} circuit breaker is OPEN. Requests are being rejected."
```

#### CircuitBreakerOpenTooLong
Alert when a circuit breaker remains OPEN for more than 5 minutes.

```yaml
- alert: CircuitBreakerOpenTooLong
  expr: |
    increase(circuit_breaker_state_changes_total{from_state="CLOSED",to_state="OPEN"}[5m]) > 0
    and
    circuit_breaker_state == 1
  for: 5m
  labels:
    severity: critical
    component: circuit-breaker
  annotations:
    summary: "Circuit breaker OPEN for >5 min for {{ $labels.service }}"
    description: "Service {{ $labels.service }} circuit breaker has been OPEN for more than 5 minutes. Manual intervention may be required."
```

#### HighCircuitBreakerFailureRate
Alert when failure rate for a service exceeds 20% in a 5-minute window.

```yaml
- alert: HighCircuitBreakerFailureRate
  expr: |
    rate(circuit_breaker_failures_total[5m]) /
    (rate(circuit_breaker_failures_total[5m]) + rate(circuit_breaker_successes_total[5m])) > 0.2
  for: 2m
  labels:
    severity: warning
    component: circuit-breaker
  annotations:
    summary: "High failure rate for {{ $labels.service }}"
    description: "Failure rate for {{ $labels.service }} is {{ $value | humanizePercentage }}. Circuit breaker may trigger soon."
```

#### ExcessiveCircuitBreakerRetries
Alert when retry count exceeds threshold, indicating service degradation.

```yaml
- alert: ExcessiveCircuitBreakerRetries
  expr: rate(http_client_retries_total[5m]) > 0.5
  for: 2m
  labels:
    severity: warning
    component: circuit-breaker
  annotations:
    summary: "Excessive retries for {{ $labels.service }}"
    description: "Service {{ $labels.service }} is experiencing {{ $value }} retries/sec. Service may be slow or unstable."
```

### Connection Pool Alerts

#### HighConnectionPoolUtilization
Alert when connection pool utilization exceeds 90%.

```yaml
- alert: HighConnectionPoolUtilization
  expr: http_client_pool_utilization{service!=""} > 0.9
  for: 2m
  labels:
    severity: warning
    component: connection-pool
  annotations:
    summary: "High connection pool utilization for {{ $labels.service }}"
    description: "Connection pool for {{ $labels.service }} is {{ $value | humanizePercentage }} utilized. May cause connection timeouts."
```

#### ExhaustedConnectionPool
Alert when connection pool reaches maximum capacity.

```yaml
- alert: ExhaustedConnectionPool
  expr: http_client_pool_connections_active >= http_client_pool_connections_total
  for: 1m
  labels:
    severity: critical
    component: connection-pool
  annotations:
    summary: "Connection pool EXHAUSTED for {{ $labels.service }}"
    description: "Connection pool for {{ $labels.service }} is fully utilized ({{ $value }} connections). New requests will block."
```

#### HighHttpRequestLatency
Alert when p95 HTTP request latency exceeds 5 seconds.

```yaml
- alert: HighHttpRequestLatency
  expr: |
    histogram_quantile(0.95,
      rate(http_client_request_duration_seconds_bucket{status="success"}[5m])
    ) > 5
  for: 2m
  labels:
    severity: warning
    component: http-client
  annotations:
    summary: "High HTTP request latency for {{ $labels.service }}"
    description: "p95 latency for {{ $labels.service }} is {{ $value | humanizeDuration }}. Service may be overloaded."
```

### Subagent Pool Alerts

#### SubagentPoolHealthDegraded
Alert when subagent pool health score drops below 50.

```yaml
- alert: SubagentPoolHealthDegraded
  expr: subagent_pool_health_score < 50
  for: 2m
  labels:
    severity: warning
    component: subagent-pool
  annotations:
    summary: "Subagent pool health degraded"
    description: "Subagent pool health score is {{ $value }}/100. System is under pressure."
    runbook: "https://docs.maestroflow.com/runbooks/subagent-pool-health"
```

#### SubagentQueueBacklog
Alert when subagent queue depth exceeds 100 items.

```yaml
- alert: SubagentQueueBacklog
  expr: subagent_pool_queue_depth > 100
  for: 2m
  labels:
    severity: warning
    component: subagent-pool
  annotations:
    summary: "Subagent task queue backlog building up"
    description: "Queue depth is {{ $value }} tasks. Consider scaling pool or investigating slow tasks."
    runbook: "https://docs.maestroflow.com/runbooks/subagent-pool-backlog"
```

#### SubagentHighFailureRate
Alert when subagent task failure rate exceeds 10%.

```yaml
- alert: SubagentHighFailureRate
  expr: |
    rate(subagent_tasks_total{status="failure"}[5m]) /
    rate(subagent_tasks_total[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
    component: subagent-pool
  annotations:
    summary: "High subagent task failure rate"
    description: "Subagent failure rate is {{ $value | humanizePercentage }}. Investigate failing tasks."
```

#### SubagentPoolExhausted
Alert when all workers are active and queue is growing.

```yaml
- alert: SubagentPoolExhausted
  expr: |
    subagent_pool_active_workers >= subagent_pool_size
    and
    subagent_pool_pending_tasks > 0
  for: 1m
  labels:
    severity: warning
    component: subagent-pool
  annotations:
    summary: "Subagent pool fully utilized"
    description: "All {{ $value }} workers are active. Dynamic scaling should adjust pool size."
```

### System Resource Alerts

#### HighCPUUtilization
Alert when system CPU utilization exceeds 85% for 3 minutes.

```yaml
- alert: HighCPUUtilization
  expr: subagent_pool_cpu_utilization > 85
  for: 3m
  labels:
    severity: warning
    component: system
  annotations:
    summary: "High system CPU utilization"
    description: "CPU utilization is {{ $value }}%. System capacity is constrained."
    action: "Check for long-running tasks, consider reducing load or scaling infrastructure."
```

#### CriticalCPUUtilization
Alert when system CPU utilization exceeds 95%.

```yaml
- alert: CriticalCPUUtilization
  expr: subagent_pool_cpu_utilization > 95
  for: 1m
  labels:
    severity: critical
    component: system
  annotations:
    summary: "CRITICAL system CPU utilization"
    description: "CPU utilization is {{ $value }}%. System is at capacity limit."
    action: "Immediate action required: Check running processes, kill non-critical tasks, or scale infrastructure."
```

#### HighMemoryUtilization
Alert when system memory utilization exceeds 85% for 3 minutes.

```yaml
- alert: HighMemoryUtilization
  expr: subagent_pool_memory_utilization > 85
  for: 3m
  labels:
    severity: warning
    component: system
  annotations:
    summary: "High system memory utilization"
    description: "Memory utilization is {{ $value }}%. System memory is constrained."
    action: "Check for memory leaks, consider reducing concurrency or scaling infrastructure."
```

#### CriticalMemoryUtilization
Alert when system memory utilization exceeds 95%.

```yaml
- alert: CriticalMemoryUtilization
  expr: subagent_pool_memory_utilization > 95
  for: 1m
  labels:
    severity: critical
    component: system
  annotations:
    summary: "CRITICAL system memory utilization"
    description: "Memory utilization is {{ $value }}%. System is at capacity limit."
    action: "Immediate action required: Free memory or gracefully shutdown non-essential processes."
```

## Alert Routing

### Notification Channels

```yaml
# Slack notifications for warnings
- match:
    severity: warning
  receiver: slack-alerts
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

# PagerDuty for critical alerts
- match:
    severity: critical
  receiver: pagerduty
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 15m
```

## Metrics for Alerting Rules

### Prometheus Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'maestroflow'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s

rule_files:
  - '/path/to/maestroflow-alerts.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
```

## Alert Handling Procedures

### CircuitBreakerOpen

**Detection**: Circuit breaker for a service transitions to OPEN state

**Response**:
1. Check service health: `GET /api/health/services`
2. Review service logs for errors
3. If service is recovering, alert will auto-resolve
4. If service is down, escalate to on-call engineer
5. Consider manual circuit reset if service is healthy

**Runbook**: [Circuit Breaker Recovery](./runbooks/circuit-breaker-recovery.md)

### HighConnectionPoolUtilization

**Detection**: Connection pool utilization > 90% for 2 minutes

**Response**:
1. Check active HTTP requests: `GET /metrics | grep http_client_requests_total`
2. Identify which service is consuming connections
3. Check if service is slow or hanging
4. If slow: service may need optimization
5. If hanging: may need to close stale connections
6. Consider increasing pool size if legitimate load

**Runbook**: [Connection Pool Tuning](./runbooks/connection-pool-tuning.md)

### SubagentQueueBacklog

**Detection**: Subagent queue depth > 100 for 2 minutes

**Response**:
1. Check pool metrics: `GET /api/health/subagent-pool`
2. Check if pool is at capacity: `subagent_pool_active_workers >= subagent_pool_size`
3. Check task duration: high latency means tasks are slow
4. Check system resources: CPU/memory may be constrained
5. Options:
   - Wait for dynamic pool adjustment (30-second interval)
   - Manually scale pool if needed
   - Identify slow tasks and optimize

**Runbook**: [Subagent Pool Scaling](./runbooks/subagent-pool-scaling.md)

### HighCPUUtilization

**Detection**: System CPU > 85% for 3 minutes

**Response**:
1. Identify CPU-consuming processes: `top -o %CPU`
2. Check if subagent pool is at max size
3. Check for long-running tasks
4. Options:
   - Reduce concurrent subagent count (pool will auto-adjust)
   - Kill non-critical processes
   - Scale infrastructure
5. Monitor CPU trend to see if it's temporary or sustained

**Runbook**: [System Resource Management](./runbooks/system-resources.md)

## Testing Alerts

### Manual Alert Testing

```bash
# Trigger circuit breaker open (requires load)
curl -X GET http://localhost:8000/api/health/services

# Trigger high queue depth (requires many subagent tasks)
# Submit 200+ subagent tasks:
for i in {1..200}; do
  curl -X POST http://localhost:8000/api/subagents/execute \
    -d '{"task":"test task '$i'"}' &
done

# Monitor alerts
curl http://localhost:9093/api/v1/alerts
```

### Prometheus Queries for Validation

```promql
# Verify circuit breaker state changes are tracked
increase(circuit_breaker_state_changes_total[1h])

# Verify pool metrics are being collected
subagent_pool_size

# Verify HTTP requests are tracked
rate(http_client_requests_total[5m])
```

## Escalation Procedures

### P1 Critical Alerts (Immediate)

- CriticalCPUUtilization
- CriticalMemoryUtilization
- ExhaustedConnectionPool
- CircuitBreakerOpenTooLong

**Action**: Page on-call engineer immediately

### P2 Warning Alerts (15 minutes)

- HighCPUUtilization
- HighMemoryUtilization
- HighConnectionPoolUtilization
- SubagentPoolExhausted

**Action**: Team lead review, escalate if needed

### P3 Informational (Passive monitoring)

- HighCircuitBreakerFailureRate
- SubagentHighFailureRate

**Action**: Review trends, adjust configuration proactively
