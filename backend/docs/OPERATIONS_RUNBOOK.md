# Resilience Operations Runbook

This runbook provides operational procedures for monitoring, troubleshooting, and tuning the MaestroFlow resilience system in production.

---

## Table of Contents

1. [Monitoring Circuit Breakers](#monitoring-circuit-breakers)
2. [Manual Circuit Reset](#manual-circuit-reset)
3. [Pool Tuning Guidelines](#pool-tuning-guidelines)
4. [Troubleshooting Degraded Performance](#troubleshooting-degraded-performance)
5. [Incident Response](#incident-response)
6. [Alerts & Escalation](#alerts--escalation)

---

## Monitoring Circuit Breakers

### Real-Time Dashboard

Access the health dashboard to view all circuit breaker states:

```bash
# Get all service health
curl http://localhost:8001/api/health/services | jq '.services[] | {name, state, healthy, error_rate}'

# Example output:
# {
#   "name": "surfsense",
#   "state": "closed",
#   "healthy": true,
#   "error_rate": 0.02
# }
```

### Key Indicators

| Indicator | Healthy | Warning | Critical |
|-----------|---------|---------|----------|
| Circuit State | CLOSED | HALF_OPEN | OPEN |
| Error Rate | < 5% | 5-20% | > 20% |
| Response Time P95 | < 1s | 1-5s | > 5s |
| Pool Utilization | < 70% | 70-85% | > 85% |
| Queue Depth | < pool_size | pool_size - 2x | > 2x pool_size |

### Prometheus Monitoring

Query health metrics directly from Prometheus:

```promql
# Circuit breaker state (1=OPEN, 2=HALF_OPEN, 0=CLOSED)
circuit_breaker_state{service="surfsense"}

# Failure rate over 5 minutes
rate(circuit_breaker_failures_total[5m])

# Success rate (percentage)
100 * rate(circuit_breaker_successes_total[5m]) / (rate(circuit_breaker_failures_total[5m]) + rate(circuit_breaker_successes_total[5m]))

# Time since last state change
time() - circuit_breaker_last_state_change_timestamp

# Requests rejected due to open circuit
rate(circuit_breaker_rejected_requests_total[5m])
```

### Log Analysis

Search logs for circuit breaker events:

```bash
# Watch for circuit state transitions
tail -f /var/log/maestroflow/backend.log | grep -E "circuit_(opened|closed|half_open)"

# Count failures per service (recent hour)
grep "circuit_failure" /var/log/maestroflow/backend.log | \
  awk -F'service=' '{print $2}' | \
  awk '{print $1}' | sort | uniq -c

# Find slow requests (> 5s)
grep "http_request_duration_seconds" /var/log/maestroflow/backend.log | \
  awk -F'duration=' '{print $2}' | \
  awk '$1 > 5 {print}' | sort -rn | head -20
```

---

## Manual Circuit Reset

### When to Reset

Reset a circuit manually when:
1. Service has recovered but circuit remains open
2. Need to immediately restore access for user testing
3. False positive cascade (service actually healthy)
4. Maintenance complete and need immediate traffic restoration

### Safe Reset Procedure

**NEVER reset without verifying service health first.**

```bash
# 1. Verify service health (e.g., SurfSense)
curl -I https://api.surfsense.io/health
# Expected: HTTP 200

# 2. Test with a single request
curl https://api.surfsense.io/search?query=test \
  --max-time 5 \
  --retry 1

# 3. Check current circuit state
curl http://localhost:8001/api/health/services | jq '.services[] | select(.name=="surfsense")'

# 4. Reset circuit (if healthy)
# Option A: Restart the service (safest)
docker-compose restart maestroflow-backend

# Option B: Use admin API (if implemented)
curl -X POST http://localhost:8001/api/admin/circuit-reset \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service": "surfsense"}'

# 5. Verify state changed to CLOSED
sleep 2
curl http://localhost:8001/api/health/services | jq '.services[] | select(.name=="surfsense")'
```

### Automated Recovery

The system automatically transitions circuits from OPEN → HALF_OPEN → CLOSED when:
1. `CIRCUIT_RESET_TIMEOUT` seconds have elapsed (default: 60s)
2. A request is sent to the half-open circuit
3. Request succeeds
4. `CIRCUIT_SUCCESS_THRESHOLD` consecutive successes recorded (default: 2)

**Do not manually reset unless recovery is taking too long.**

---

## Pool Tuning Guidelines

### Diagnosing Pool Issues

#### Symptom: Queue Backlog Increasing

**Indicators:**
```bash
# Queue depth > 2x pool size
curl http://localhost:8001/api/health/subagent-pool | \
  jq '.metrics | {queue_depth, pool_size}'

# Response time P99 > 5s
curl http://localhost:8001/api/health/subagent-pool | \
  jq '.metrics.response_time_p99_ms'
```

**Root Cause Analysis:**
1. Is CPU high (> 80%)? → System constrained, can't add workers
2. Is memory high (> 85%)? → System constrained, can't add workers
3. Is load sustained or temporary spike?

**Fix:**
```bash
# Option 1: Increase initial pool size (for sustained high load)
export POOL_INITIAL_SIZE=16
docker-compose restart maestroflow-backend

# Option 2: Increase max pool size (allow more workers)
export POOL_MAX_SIZE=32
docker-compose restart maestroflow-backend

# Option 3: Lower scale-up threshold (scale more aggressively)
export POOL_SCALE_UP_THRESHOLD=1.5
# No restart needed - takes effect at next adjustment cycle
```

#### Symptom: High CPU Usage from Pool

**Indicators:**
```bash
docker stats maestroflow-backend | grep CPU
# Expected: < 50%, Warning: > 80%, Critical: > 95%
```

**Root Cause Analysis:**
1. Too many concurrent workers processing CPU-intensive tasks
2. Context switching overhead from over-provisioned pool
3. Subagent tasks are CPU-bound (code execution)

**Fix:**
```bash
# Option 1: Reduce max pool size
export POOL_MAX_SIZE=8
docker-compose restart maestroflow-backend

# Option 2: Increase scale-down threshold (shrink faster)
export POOL_SCALE_DOWN_THRESHOLD=0.3
# Takes effect at next adjustment cycle

# Option 3: Increase CPU threshold (prevent further scaling)
export CPU_PREVENT_SCALE_THRESHOLD=70
```

#### Symptom: Memory Growing Over Time

**Indicators:**
```bash
# Memory usage increasing without corresponding load increase
docker stats --no-stream maestroflow-backend | grep Memory

# Check for memory leaks in connection pool
curl http://localhost:8001/api/health/services | jq '.services[] | {name, active_connections}'
```

**Root Cause Analysis:**
1. Connection pool keeping too many keep-alive connections
2. Event queue in Langfuse not flushing
3. Metric buffers not rotating

**Fix:**
```bash
# Option 1: Reduce keep-alive connections
export HTTP_POOL_KEEPALIVE=10
docker-compose restart maestroflow-backend

# Option 2: Reduce max pool connections
export HTTP_POOL_MAX_CONNECTIONS=50
docker-compose restart maestroflow-backend

# Option 3: Monitor Langfuse queue depth
curl http://localhost:8001/api/health/langfuse | \
  jq '.metrics.event_queue_depth'

# If queue depth growing: check if Langfuse circuit is open
curl http://localhost:8001/api/health/services | \
  jq '.services[] | select(.name=="langfuse")'
```

### Recommended Configurations by Workload

#### High-Throughput (Many Concurrent Users)

```bash
export POOL_INITIAL_SIZE=16
export POOL_MAX_SIZE=32
export POOL_SCALE_UP_THRESHOLD=1.5
export POOL_SCALE_DOWN_THRESHOLD=0.3
export POOL_ADJUST_INTERVAL=10

export HTTP_POOL_MAX_CONNECTIONS=200
export CIRCUIT_FAILURE_THRESHOLD=10
```

#### Steady-State (Predictable Load)

```bash
export POOL_INITIAL_SIZE=8
export POOL_MAX_SIZE=16
export POOL_SCALE_UP_THRESHOLD=2.0
export POOL_SCALE_DOWN_THRESHOLD=0.5
export POOL_ADJUST_INTERVAL=30

export HTTP_POOL_MAX_CONNECTIONS=100
export CIRCUIT_FAILURE_THRESHOLD=5
```

#### Resource-Constrained (Edge, Limited CPU/Memory)

```bash
export POOL_INITIAL_SIZE=2
export POOL_MAX_SIZE=4
export POOL_SCALE_UP_THRESHOLD=4.0
export POOL_SCALE_DOWN_THRESHOLD=0.2
export POOL_ADJUST_INTERVAL=60

export HTTP_POOL_MAX_CONNECTIONS=25
export CIRCUIT_FAILURE_THRESHOLD=2
export MAX_RETRIES=1
```

---

## Troubleshooting Degraded Performance

### Checklist: Systematic Diagnosis

```bash
#!/bin/bash
# Run this script when investigating performance issues

echo "=== CIRCUIT BREAKER STATUS ==="
curl http://localhost:8001/api/health/services | jq '.services[] | {name, state, healthy}'

echo -e "\n=== SUBAGENT POOL STATUS ==="
curl http://localhost:8001/api/health/subagent-pool | jq '.metrics | {pool_size, active_workers, queue_depth, response_time_p95_ms}'

echo -e "\n=== SYSTEM RESOURCES ==="
docker stats --no-stream maestroflow-backend | tail -1 | awk '{print "CPU: " $3 ", Memory: " $5}'

echo -e "\n=== RECENT ERRORS (Last 30 min) ==="
grep ERROR /var/log/maestroflow/backend.log | tail -20

echo -e "\n=== CIRCUIT REJECTIONS (Last 5 min) ==="
grep "circuit_rejected" /var/log/maestroflow/backend.log | tail -10

echo -e "\n=== SLOW REQUESTS (> 5s, Last hour) ==="
grep "duration_ms" /var/log/maestroflow/backend.log | \
  awk -F'duration_ms=' '{print $2}' | \
  awk '$1 > 5000 {print}' | wc -l
```

### Common Issues & Solutions

#### Issue 1: All Services Showing High Error Rate

**Diagnosis:**
```bash
# Check if it's network-wide or specific to our backend
curl -I https://api.surfsense.io/health
curl -I https://api.litellm.com/health

# Check backend logs for error patterns
grep -E "connection refused|timeout|DNS" /var/log/maestroflow/backend.log | tail -20

# Check if circuits are cascading (one service open causes others to open)
curl http://localhost:8001/api/health/services | jq '.services | map(select(.state=="open")) | length'
```

**Solution:**
1. If external services are down: Wait for recovery, circuit will auto-reset
2. If network issue: Check DNS, firewall rules, VPN connectivity
3. If cascading: Increase `CIRCUIT_FAILURE_THRESHOLD` to prevent sensitive cascades
   ```bash
   export CIRCUIT_FAILURE_THRESHOLD=10
   docker-compose restart maestroflow-backend
   ```

#### Issue 2: Queue Backlog Growing

**Diagnosis:**
```bash
# Check queue depth trend
while true; do
  curl -s http://localhost:8001/api/health/subagent-pool | jq '.metrics.queue_depth'
  sleep 5
done

# Check if pool is scaling
curl http://localhost:8001/api/health/subagent-pool | jq '.metrics | {pool_size, max_pool_size}'

# Check if CPU/memory preventing scale-up
curl http://localhost:8001/api/health/subagent-pool | jq '.metrics | {cpu_usage, memory_usage}'
```

**Solution:**
1. If CPU > 80%: Don't scale up further, reduce load or optimize code
2. If memory > 85%: Reduce keep-alive connections (see earlier section)
3. If resources low: Increase queue processing timeout, allow requests to fail faster
   ```bash
   export CIRCUIT_TIMEOUT=5
   ```

#### Issue 3: Specific Service Stuck in OPEN State

**Diagnosis:**
```bash
# How long has it been open?
curl http://localhost:8001/api/health/services | jq '.services[] | select(.name=="service_name") | .open_since'

# How many failures triggered this?
grep "circuit_failure.*surfsense" /var/log/maestroflow/backend.log | tail -20

# Is the underlying service actually healthy?
curl -I https://api.service.com/health --max-time 10
```

**Solution:**
1. If service is healthy: Manually reset (follow procedure above)
2. If service is flaky: Increase `CIRCUIT_RESET_TIMEOUT` to allow more recovery time
   ```bash
   export CIRCUIT_RESET_TIMEOUT=300  # 5 minutes instead of 60 seconds
   ```
3. If service frequently fails: Increase failure threshold, reduce timeout
   ```bash
   export CIRCUIT_FAILURE_THRESHOLD=8
   export CIRCUIT_TIMEOUT=60  # Allow longer for expensive operations
   ```

---

## Incident Response

### On-Call Protocol

**Pager Alert:** Circuit breaker open > 5 minutes

1. **Acknowledge:** Confirm receipt in status page
2. **Assess:** Run diagnostic checklist (above)
3. **Communicate:** Update status page with findings
4. **Remediate:** Apply fix from troubleshooting guide
5. **Verify:** Confirm service recovery
6. **Post-Mortem:** Document in incident log

### Escalation Matrix

| Condition | Severity | Response Time | Escalation |
|-----------|----------|---------------|-----------|
| 1 service OPEN < 5m | INFO | 15m | None |
| 1 service OPEN > 5m | WARNING | 5m | Team lead |
| 2+ services OPEN | WARNING | 5m | Team lead |
| Circuit cascade (>3 open) | CRITICAL | 5m | On-call eng |
| System unresponsive | CRITICAL | 2m | Page eng |
| Queue backlog > 1000 | CRITICAL | 5m | Page eng |

### Incident Communication Template

```
Subject: [Incident] Service Degradation - SurfSense Circuit Open

Timeline:
- 14:32 UTC: Circuit breaker opened (failure threshold: 5)
- 14:35 UTC: Alert triggered
- 14:37 UTC: Diagnosed - SurfSense API returning 500 errors

Root Cause:
- SurfSense experiencing upstream database failure
- Generated 50+ consecutive errors in < 2 minutes
- Triggered automatic circuit open

Actions Taken:
- Verified SurfSense status page (confirmed issue)
- Notified SurfSense support (case #12345)
- Increased circuit reset timeout to allow recovery
- User impact: Failed requests return 503 with fallback message

Resolution:
- SurfSense issue resolved at 14:55 UTC
- Circuit auto-recovered at 15:01 UTC (60s + 2 success threshold)
- Normal service restored

Prevention:
- Increase CIRCUIT_RESET_TIMEOUT to 120s to better handle transient outages
- Add SMS alerts for circuit open > 10 minutes
```

---

## Alerts & Escalation

### Prometheus Alert Rules

See `/backend/config/prometheus-alerts.yml` for complete rules. Key alerts:

```yaml
# Critical: Circuit open > 5 minutes
alert: CircuitBreakerOpenTooLong
expr: |
  circuit_breaker_state{state="open"} == 1 
  and 
  (time() - circuit_breaker_last_state_change_timestamp) > 300
for: 1m
labels:
  severity: critical

# Warning: High error rate
alert: HighErrorRate
expr: |
  rate(circuit_breaker_failures_total[5m]) / 
  (rate(circuit_breaker_failures_total[5m]) + rate(circuit_breaker_successes_total[5m])) 
  > 0.2
for: 5m
labels:
  severity: warning

# Warning: Queue backlog
alert: SubagentQueueBacklog
expr: subagent_pool_queue_depth > subagent_pool_size * 2
for: 5m
labels:
  severity: warning
```

### On-Call Dashboard

Display this Grafana dashboard for ongoing monitoring:

```json
{
  "dashboard": "Resilience Monitoring",
  "panels": [
    {
      "title": "Circuit Breaker State",
      "targets": [
        "circuit_breaker_state{service=~\"$service\"}"
      ]
    },
    {
      "title": "Error Rate (5m)",
      "targets": [
        "rate(circuit_breaker_failures_total[5m])"
      ]
    },
    {
      "title": "Subagent Pool",
      "targets": [
        "subagent_pool_size",
        "subagent_pool_active_workers",
        "subagent_pool_queue_depth"
      ]
    },
    {
      "title": "System Resources",
      "targets": [
        "process_cpu_seconds_total",
        "process_resident_memory_bytes"
      ]
    }
  ]
}
```

---

## Additional Resources

- **Configuration:** `/backend/docs/RESILIENCE_CONFIG.md`
- **Metrics Reference:** `/backend/docs/PROMETHEUS_METRICS.md`
- **Alerting Rules:** `/backend/config/prometheus-alerts.yml`
- **Circuit Breaker Source:** `src/core/resilience/circuit_breaker.py`
- **HTTP Client Manager:** `src/core/http/client_manager.py`

---

## Quick Reference

### Useful Commands

```bash
# Check all service health
curl http://localhost:8001/api/health/services | jq

# Check pool metrics
curl http://localhost:8001/api/health/subagent-pool | jq

# Restart backend (resets circuits)
docker-compose restart maestroflow-backend

# View recent errors
tail -100 /var/log/maestroflow/backend.log | grep ERROR

# Monitor real-time metrics
watch -n 1 'curl -s http://localhost:8001/api/health/services | jq ".services[] | {name, state, error_rate}"'

# Test specific service health
curl -I https://api.surfsense.io/health --max-time 10

# Check Prometheus queries
curl 'http://localhost:9090/api/v1/query?query=circuit_breaker_state'
```

### Critical Environment Variables

```bash
CIRCUIT_FAILURE_THRESHOLD=5       # Failures before open
CIRCUIT_RESET_TIMEOUT=60          # Seconds until half-open
POOL_MAX_SIZE=16                  # Max worker pool
POOL_SCALE_UP_THRESHOLD=2.0       # Queue depth ratio
CPU_PREVENT_SCALE_THRESHOLD=80    # CPU % limit
MEMORY_PREVENT_SCALE_THRESHOLD=85 # Memory % limit
```

---

*Last Updated: 2024-03-21*
*Runbook Owner: DevOps Team*
*On-Call: See PagerDuty*
