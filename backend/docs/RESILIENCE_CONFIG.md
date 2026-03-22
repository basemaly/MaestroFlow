# Resilience & Circuit Breaker Configuration

This guide documents all environment variables and configuration options for the MaestroFlow resilience system, including circuit breakers, connection pooling, dynamic pool sizing, and fallback mechanisms.

## Overview

The resilience system provides:
- **Circuit Breaker Pattern**: Prevents cascade failures across external services
- **Connection Pooling**: Manages HTTP connections with auto-scaling
- **Dynamic Pool Sizing**: Automatically adjusts pool size based on load
- **Graceful Degradation**: Falls back to degraded service when primary fails
- **Health Monitoring**: Tracks service health with prometheus metrics

---

## Core Circuit Breaker Configuration

### Environment Variables

All circuit breaker settings use the `CIRCUIT_` prefix:

| Variable | Default | Range | Purpose |
|----------|---------|-------|---------|
| `CIRCUIT_FAILURE_THRESHOLD` | 5 | 1-100 | Number of consecutive failures before circuit opens |
| `CIRCUIT_SUCCESS_THRESHOLD` | 2 | 1-10 | Number of successes in half-open before circuit closes |
| `CIRCUIT_RESET_TIMEOUT` | 60 | 1-3600 | Seconds to wait before transitioning from open to half-open |
| `CIRCUIT_TIMEOUT` | 30 | 1-300 | Request timeout in seconds (varies per service) |
| `MAX_RETRIES` | 3 | 0-10 | Maximum retry attempts per request |
| `CIRCUIT_RETRY_BASE_DELAY` | 1.0 | 0.1-10.0 | Base delay in seconds for exponential backoff |
| `CIRCUIT_RETRY_MAX_DELAY` | 30.0 | 1.0-300.0 | Maximum delay between retries in seconds |
| `CIRCUIT_RETRY_JITTER` | true | true/false | Add random jitter to retry delays (prevents thundering herd) |

### Configuration Example

```bash
# Strict circuit breaker (fail fast)
export CIRCUIT_FAILURE_THRESHOLD=3
export CIRCUIT_RESET_TIMEOUT=30
export CIRCUIT_TIMEOUT=10
export MAX_RETRIES=1

# Lenient circuit breaker (retry aggressively)
export CIRCUIT_FAILURE_THRESHOLD=10
export CIRCUIT_RESET_TIMEOUT=120
export CIRCUIT_TIMEOUT=60
export MAX_RETRIES=5
```

---

## Service-Specific Configuration

Each external service has tailored circuit breaker settings. These are defined in `src/core/http/initialization.py` and override global defaults.

### SurfSense (Web Scraping)

```bash
export SURFSENSE_API_URL=https://api.surfsense.io
export SURFSENSE_API_KEY=<your-key>
export SURFSENSE_CIRCUIT_BREAKER_ENABLED=true
export SURFSENSE_FALLBACK_URL=<optional-fallback>
```

**Built-in Settings:**
- Timeout: 30.0s (allowing for long scraping operations)
- Max Retries: 3
- Failure Threshold: 5
- Success Threshold: 2
- Reset Timeout: 60s

### LiteLLM (LLM Proxy)

```bash
export LITELLM_API_BASE=http://localhost:8000  # Or cloud endpoint
export LITELLM_PROXY_BASE_URL=http://localhost:8000
export LITELLM_API_KEY=<your-key>
```

**Built-in Settings:**
- Timeout: 60.0s (longer for expensive LLM operations)
- Max Retries: 2 (fewer retries for expensive operations)
- Failure Threshold: 3
- Success Threshold: 2
- Reset Timeout: 120.0s

**Recommended:**
- Use local proxy to reduce network latency
- Set `LITELLM_PROXY_BASE_URL` to enable circuit breaker routing

### Langfuse (Observability)

```bash
export LANGFUSE_PUBLIC_KEY=<your-key>
export LANGFUSE_SECRET_KEY=<your-secret>
export LANGFUSE_HOST=https://cloud.langfuse.com  # or self-hosted
```

**Built-in Settings:**
- Timeout: 5.0s (short timeout - observability should not block)
- Max Retries: 1 (minimal retries to prevent overhead)
- Failure Threshold: 3
- Success Threshold: 1
- Reset Timeout: 30.0s

**Recommended:**
- Set short timeout to prevent observability from impacting main path
- Events are queued when circuit is open, flushed when recovered

### LangGraph

```bash
export LANGGRAPH_API_URL=<langgraph-server-url>
```

**Built-in Settings:**
- Timeout: 30.0s
- Max Retries: 3
- Reset Timeout: 60.0s

### Other Services

OpenViking, ActivePieces, BrowserRuntime, StateWeave all follow similar patterns with 30s timeout, 3 retries, 60s reset timeout.

---

## Connection Pool Configuration

### Global Pool Settings

| Variable | Default | Purpose |
|----------|---------|---------|
| `HTTP_POOL_MAX_CONNECTIONS` | 100 | Maximum connections per pool |
| `HTTP_POOL_KEEPALIVE` | 50 | Number of keep-alive connections |
| `HTTP_POOL_TIMEOUT` | 30.0 | Connection timeout in seconds |
| `HTTP_CONNECT_TIMEOUT` | 10.0 | Initial connection timeout |

### Per-Service Pool Override

```bash
# Override for specific service (example: SurfSense)
export SURFSENSE_POOL_MAX_CONNECTIONS=50
export SURFSENSE_POOL_KEEPALIVE=25
```

---

## Dynamic Pool Sizing Configuration

The subagent executor automatically adjusts the worker pool based on load and system resources.

### Environment Variables

| Variable | Default | Range | Purpose |
|----------|---------|-------|---------|
| `POOL_MIN_SIZE` | 2 | 1-8 | Minimum worker pool size |
| `POOL_MAX_SIZE` | 16 | 8-64 | Maximum worker pool size |
| `POOL_INITIAL_SIZE` | 8 | 2-16 | Starting worker pool size |
| `POOL_ADJUST_INTERVAL` | 30 | 5-300 | Seconds between pool size adjustments |
| `POOL_SCALE_UP_THRESHOLD` | 2.0 | 1.0-5.0 | Queue depth ratio to trigger scale-up |
| `POOL_SCALE_DOWN_THRESHOLD` | 0.5 | 0.1-2.0 | Queue depth ratio to trigger scale-down |

### Resource Constraint Thresholds

| Variable | Default | Purpose |
|----------|---------|---------|
| `CPU_PREVENT_SCALE_THRESHOLD` | 80 | CPU % above which pool won't scale up |
| `CPU_REDUCE_SCALE_THRESHOLD` | 90 | CPU % above which pool scales down |
| `MEMORY_PREVENT_SCALE_THRESHOLD` | 85 | Memory % above which pool won't scale up |
| `MEMORY_REDUCE_SCALE_THRESHOLD` | 95 | Memory % above which pool scales down |

### Configuration Example

```bash
# Aggressive scaling (for high-throughput)
export POOL_MIN_SIZE=4
export POOL_MAX_SIZE=32
export POOL_INITIAL_SIZE=16
export POOL_ADJUST_INTERVAL=10
export POOL_SCALE_UP_THRESHOLD=1.5
export CPU_PREVENT_SCALE_THRESHOLD=70
export MEMORY_PREVENT_SCALE_THRESHOLD=75

# Conservative scaling (for resource-constrained)
export POOL_MIN_SIZE=2
export POOL_MAX_SIZE=8
export POOL_INITIAL_SIZE=4
export POOL_ADJUST_INTERVAL=60
export POOL_SCALE_UP_THRESHOLD=3.0
export CPU_PREVENT_SCALE_THRESHOLD=85
export MEMORY_PREVENT_SCALE_THRESHOLD=90
```

---

## Fallback Configuration

### Primary Fallback Setup

Most services support optional fallback URLs for degraded operation:

```bash
# SurfSense fallback
export SURFSENSE_FALLBACK_URL=https://fallback-surfsense.example.com

# Langfuse fallback (events queued locally instead)
# Langfuse does NOT use fallback URL - uses event queue instead
```

### How Fallback Works

1. **Primary circuit opens** → fallback URL is used automatically
2. **Fallback enabled** → requests route to fallback without user intervention
3. **Fallback disabled** → requests rejected with 503 Service Unavailable
4. **Recovery** → primary circuit closes, requests route back to primary

---

## Observability Configuration

### Prometheus Metrics

Metrics are automatically exported to `/metrics` endpoint:

```bash
export METRICS_PORT=9090
export METRICS_ENABLED=true
```

**Key Metrics:**
- `circuit_breaker_state` - Current state (0=closed, 1=open, 2=half-open)
- `circuit_breaker_failures_total` - Total failures recorded
- `circuit_breaker_successes_total` - Total successes recorded
- `http_client_requests_total` - Total HTTP requests per service
- `http_client_request_duration_seconds` - Request latency histogram
- `subagent_pool_size` - Current worker pool size
- `subagent_pool_queue_depth` - Tasks waiting in queue

### Structured Logging

All resilience events are logged with structured format:

```bash
export LOG_LEVEL=INFO
export LOG_FORMAT=json  # or 'text'
```

**Logged Events:**
- Circuit state transitions
- Failure and success counts
- Pool size adjustments
- Recovery milestones

### Health Check Endpoint

Monitor overall system health:

```bash
curl http://localhost:8001/api/health/services
curl http://localhost:8001/api/health/subagent-pool
curl http://localhost:8001/api/health/shutdown-status
```

---

## Complete Configuration Example

### Development Configuration

```bash
# Lenient circuit breaker (allow retries)
export CIRCUIT_FAILURE_THRESHOLD=5
export CIRCUIT_RESET_TIMEOUT=60
export CIRCUIT_TIMEOUT=30
export MAX_RETRIES=3

# Relaxed pool sizing (favor throughput)
export POOL_MIN_SIZE=2
export POOL_MAX_SIZE=16
export POOL_INITIAL_SIZE=8
export CPU_PREVENT_SCALE_THRESHOLD=80
export MEMORY_PREVENT_SCALE_THRESHOLD=85

# Observability
export LOG_LEVEL=DEBUG
export METRICS_ENABLED=true

# Services
export LITELLM_PROXY_BASE_URL=http://localhost:8000
export LANGFUSE_PUBLIC_KEY=dev-key
export SURFSENSE_API_KEY=dev-key
```

### Production Configuration

```bash
# Strict circuit breaker (fail fast, protect resources)
export CIRCUIT_FAILURE_THRESHOLD=3
export CIRCUIT_RESET_TIMEOUT=120
export CIRCUIT_TIMEOUT=15
export MAX_RETRIES=2

# Conservative pool sizing (protect system)
export POOL_MIN_SIZE=2
export POOL_MAX_SIZE=8
export POOL_INITIAL_SIZE=4
export POOL_ADJUST_INTERVAL=30
export CPU_PREVENT_SCALE_THRESHOLD=75
export MEMORY_PREVENT_SCALE_THRESHOLD=80

# Observability
export LOG_LEVEL=INFO
export METRICS_ENABLED=true
export LANGFUSE_PUBLIC_KEY=<production-key>
export SURFSENSE_API_KEY=<production-key>

# Fallbacks
export SURFSENSE_FALLBACK_URL=https://backup-surfsense.internal
```

---

## Tuning Guidelines

### High Throughput (SaaS, High Concurrency)

```bash
# Aggressive scaling
export POOL_MIN_SIZE=8
export POOL_MAX_SIZE=32
export POOL_SCALE_UP_THRESHOLD=1.5

# Lenient circuit breaker
export CIRCUIT_FAILURE_THRESHOLD=10
export CIRCUIT_RESET_TIMEOUT=30
```

### Resource Constrained (Edge, Embedded)

```bash
# Conservative scaling
export POOL_MIN_SIZE=1
export POOL_MAX_SIZE=4
export POOL_SCALE_UP_THRESHOLD=4.0

# Strict circuit breaker
export CIRCUIT_FAILURE_THRESHOLD=2
export CIRCUIT_RESET_TIMEOUT=180
export MAX_RETRIES=1
```

### Stable/Reliable Services

```bash
# More lenient (assume service mostly works)
export CIRCUIT_FAILURE_THRESHOLD=10
export CIRCUIT_RESET_TIMEOUT=60
export MAX_RETRIES=5
```

### Flaky/Unreliable Services

```bash
# Strict (protect against cascades)
export CIRCUIT_FAILURE_THRESHOLD=3
export CIRCUIT_RESET_TIMEOUT=30
export MAX_RETRIES=2
export CIRCUIT_TIMEOUT=5  # Short timeout
```

---

## Health Check & Monitoring

### Local Testing

```bash
# Check service health
curl http://localhost:8001/api/health/services | jq '.services'

# Check subagent pool
curl http://localhost:8001/api/health/subagent-pool | jq '.metrics'

# Check shutdown status
curl http://localhost:8001/api/health/shutdown-status
```

### Prometheus Queries

```promql
# Circuit breaker state (1=OPEN)
circuit_breaker_state{service="surfsense"}

# Request success rate
rate(circuit_breaker_successes_total[5m]) / rate(circuit_breaker_failures_total[5m] + circuit_breaker_successes_total[5m])

# Pool utilization
subagent_pool_active_workers / subagent_pool_size

# Queue backlog
subagent_pool_queue_depth
```

---

## Troubleshooting

### Circuit Breaker Stuck in OPEN State

**Symptom:** Requests always rejected, never recover
**Cause:** Reset timeout too short, or service still unhealthy
**Fix:**
```bash
# Increase reset timeout
export CIRCUIT_RESET_TIMEOUT=300

# Or temporarily disable circuit breaker
# (edit code to set use_circuit_breaker=False)
```

### Pool Size Not Adjusting

**Symptom:** Pool size stuck, not responding to load
**Cause:** psutil not installed, or adjustment interval too long
**Fix:**
```bash
pip install psutil>=5.9.0
export POOL_ADJUST_INTERVAL=10  # More frequent checks
```

### High Memory Usage

**Symptom:** Memory grows over time
**Cause:** Connection pool not releasing connections
**Fix:**
```bash
export HTTP_POOL_KEEPALIVE=10  # Reduce keep-alive connections
export HTTP_POOL_MAX_CONNECTIONS=50  # Lower max connections
```

### Slow Response Times Under Load

**Symptom:** P99 latency > 5 seconds
**Cause:** Pool exhausted, requests queuing
**Fix:**
```bash
export POOL_INITIAL_SIZE=16  # Start with larger pool
export POOL_SCALE_UP_THRESHOLD=1.5  # Scale more aggressively
export CIRCUIT_TIMEOUT=5  # Fail faster on slow requests
```

---

## See Also

- **Metrics Documentation:** `/backend/docs/PROMETHEUS_METRICS.md`
- **Alerting Rules:** `/backend/docs/ALERTING_RULES.md`
- **Operations Runbook:** `/backend/docs/OPERATIONS_RUNBOOK.md`
- **Circuit Breaker Implementation:** `src/core/resilience/circuit_breaker.py`
- **HTTP Client Manager:** `src/core/http/client_manager.py`
- **Subagent Executor:** `src/subagents/executor.py`
