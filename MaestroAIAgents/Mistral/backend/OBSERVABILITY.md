---
type: reference
title: MaestroFlow Observability Guide
created: 2026-03-21
tags:
  - monitoring
  - observability
  - prometheus
  - langfuse
  - architecture
---

# MaestroFlow Observability System

## Overview

MaestroFlow includes a comprehensive observability system spanning **Prometheus metrics**, **Langfuse distributed tracing**, and **health checks**. This system enables real-time visibility into application performance, cost tracking for LLM calls, and proactive alerting.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Request enters → MetricsMiddleware                   │  │
│  │    (initializes request context, starts timer)        │  │
│  │                ↓                                       │  │
│  │  Your handler code (instrumented):                    │  │
│  │    - Database queries timed                           │  │
│  │    - Cache hits/misses tracked                        │  │
│  │    - LLM calls traced                                 │  │
│  │    - Queue operations monitored                       │  │
│  │                ↓                                       │  │
│  │  Response returned + trace sent                       │  │
│  │    - Metrics recorded locally                         │  │
│  │    - Trace sent async to Langfuse                     │  │
│  │    - Response includes trace_id header                │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Health Checks:                                            │
│  /health         → Full status (database, queue, memory)   │
│  /health/ready   → Readiness (app can serve traffic)       │
│  /health/live    → Liveness (app is running)               │
│  /metrics        → Prometheus metrics (text format)        │
└─────────────────────────────────────────────────────────────┘
    ↓                    ↓                        ↓
 Prometheus          Langfuse                   Health
 (metrics)           (traces)              (load balancers)
    ↓                    ↓
 Grafana          Langfuse UI
 (dashboards)     (trace viewer)
    ↓
 AlertManager
 (Slack/PagerDuty)
```

---

## Components

### 1. Prometheus Metrics Collection

**Module:** `src/observability/metrics.py`

Collects time-series metrics via the Prometheus client library. Metrics are exposed at `/metrics` endpoint in Prometheus text format.

#### Metric Categories

| Category | Metrics | Purpose |
|----------|---------|---------|
| **Connection Pool** | `db_connections_active`, `db_connections_total`, `db_connection_wait_seconds` | Monitor database pool health and bottlenecks |
| **Database** | `db_query_duration_seconds` (histogram) | Track query performance by type |
| **HTTP Requests** | `http_request_duration_seconds`, `http_requests_total` | Monitor endpoint latency and throughput |
| **Queues** | `queue_depth`, `queue_processed_total`, `queue_processing_latency_seconds` | Capacity planning and SLA tracking |
| **Cache** | `cache_hits_total`, `cache_misses_total`, `cache_hit_ratio` | Cache effectiveness analysis |
| **WebSocket** | `websocket_connections_active`, `websocket_messages_sent_total`, `websocket_connection_duration_seconds` | Real-time connection monitoring |
| **Memory** | `process_memory_usage_bytes` | Memory leak detection |

#### Adding New Metrics

```python
from src.observability import get_metrics

metrics = get_metrics()

# Counter (monotonically increasing)
metrics.http_requests_total.labels(method='POST', endpoint='/approvals', status=200).inc()

# Gauge (can go up or down)
metrics.queue_depth.labels(queue_name='approvals').set(42)

# Histogram (measures duration/size distributions)
metrics.db_query_duration_seconds.labels(query_type='SELECT').observe(0.045)
```

#### Context Managers for Timing

```python
from src.observability import get_metrics

metrics = get_metrics()

# Time a database query
with metrics.time_query('SELECT * FROM users'):
    result = await db.fetch('SELECT * FROM users')

# Time connection acquisition
with metrics.time_connection_wait(pool_name='main'):
    conn = await pool.acquire()
```

---

### 2. Langfuse Distributed Tracing

**Module:** `src/observability/langfuse_client.py`

Provides end-to-end request tracing with automatic correlation across service calls. Each trace includes:

- **Request ID** — unique identifier for request correlation
- **User ID** — identifies which user made the request
- **LLM Calls** — model, prompt, completion, token counts, cost
- **Database Calls** — queries executed, latency
- **Errors** — stack traces with full context

#### Trace Context Propagation

Request context is initialized by `MetricsMiddleware` and available throughout the request lifecycle via Python's `contextvars`:

```python
from src.observability.context import get_request_context

# In any handler or async function within the request
ctx = get_request_context()
print(f"Trace ID: {ctx.trace_id}")
print(f"User ID: {ctx.user_id}")
print(f"Request ID: {ctx.request_id}")
```

#### LLM Call Tracing

```python
from src.observability.llm_tracing import trace_llm_call

# Automatic tracing of LLM calls
completion = await trace_llm_call(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7,
)
```

The system automatically:
- Captures prompt and completion tokens
- Calculates cost based on model pricing
- Associates trace with request context
- Sends trace to Langfuse asynchronously

---

### 3. Health Check Endpoints

**Module:** `src/routers/health.py`

Four endpoints for operational health monitoring:

#### GET /health

Full health check with component status.

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-21T10:15:30.123456Z",
  "checks": {
    "database": "ok",
    "queue": "ok",
    "memory": "ok"
  }
}
```

**Response (200 - degraded):**
```json
{
  "status": "degraded",
  "timestamp": "2026-03-21T10:15:30.123456Z",
  "checks": {
    "database": "ok",
    "queue": "warning: depth at 850/1000",
    "memory": "ok"
  }
}
```

**Query Parameters:**
- `?verbose=true` — Returns detailed metrics and thresholds

#### GET /health/ready

Readiness probe for load balancers. Returns 200 only if application is ready to accept traffic.

**Response (200):**
```json
{"status": "ready"}
```

**Response (503 Service Unavailable):**
```json
{"status": "not_ready", "reason": "database not available"}
```

#### GET /health/live

Liveness probe. Always returns 200 if the application process is running.

**Response (200):**
```json
{"status": "alive"}
```

#### GET /metrics

Prometheus-format metrics endpoint.

**Response (200):**
```
# HELP db_connections_active Current active database connections
# TYPE db_connections_active gauge
db_connections_active{pool_name="main"} 5

# HELP http_request_duration_seconds HTTP request latency in seconds
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{endpoint="/approvals",method="GET",le="0.005"} 10
...
```

---

## Configuration

### Environment Variables

All observability features are controlled via environment variables:

```bash
# Phase 1: Metrics
METRICS_ENABLED=true
PROMETHEUS_PORT=9090
HEALTH_CHECK_INTERVAL_SECONDS=60
MEMORY_THRESHOLD_MB=1024

# Phase 2: Tracing
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...
LANGFUSE_SAMPLE_RATE=1.0

# Phase 3: Advanced Monitoring
MEMORY_GROWTH_RATE_THRESHOLD_MB_MIN=1
QUEUE_DEPTH_ALERT_THRESHOLD_PERCENT=80
CACHE_HIT_RATIO_ALERT_THRESHOLD_PERCENT=20
```

### Configuration Loading

Configuration is loaded at application startup:

```python
from src.config.observability import load_config

config = load_config()
print(f"Metrics enabled: {config.METRICS_ENABLED}")
print(f"Langfuse enabled: {config.LANGFUSE_ENABLED}")
```

Configuration is validated early to fail fast on missing critical keys.

---

## Local Development Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with local values. For local development, you can disable Langfuse:

```bash
LANGFUSE_ENABLED=false
METRICS_ENABLED=true
```

### 3. Start Observability Stack (Docker Compose)

```bash
docker-compose up -d
```

This starts:
- **Prometheus** (http://localhost:9090) — metrics scraping and storage
- **Grafana** (http://localhost:3000) — dashboard visualization
- **Redis** (port 6379) — for caching and queue operations
- **PostgreSQL** (port 5432) — optional, for production-like setup

### 4. Start the FastAPI App

```bash
python3 backend/main.py
```

The app will:
1. Load observability configuration
2. Initialize Prometheus metrics
3. Initialize Langfuse (if enabled)
4. Start health check background tasks
5. Begin accepting requests

### 5. Verify Observability is Working

```bash
# Check health
curl http://localhost:8000/health

# View Prometheus metrics
curl http://localhost:8000/metrics

# View health/ready (for load balancers)
curl http://localhost:8000/health/ready

# View health/live (for liveness probes)
curl http://localhost:8000/health/live
```

### 6. Open Dashboards

- **Prometheus UI:** http://localhost:9090
  - Go to Status → Targets to see if the app is being scraped
  - Go to Graph to query metrics: `http_requests_total{endpoint="/approvals"}`

- **Grafana UI:** http://localhost:3000
  - Default login: admin / admin
  - Add Prometheus data source: http://prometheus:9090
  - Import pre-built dashboards (see `monitoring/grafana/dashboards/`)

- **Langfuse UI:** https://cloud.langfuse.io (if using cloud) or http://localhost:3000 (if self-hosted)
  - View traces from your application
  - Filter by trace_id, user_id, or session_id

---

## Troubleshooting

### Metrics Not Appearing in Prometheus

**Problem:** Prometheus dashboard shows "No metrics found" or scrape failures.

**Debugging Steps:**

1. Verify the app is running and returning metrics:
   ```bash
   curl http://localhost:8000/metrics
   ```
   
2. Check Prometheus configuration in `prometheus.yml`:
   ```yaml
   scrape_configs:
     - job_name: 'maestroflow'
       static_configs:
         - targets: ['localhost:8000']
   ```

3. Verify scrape interval (default: 15s):
   ```bash
   # Prometheus → Status → Targets
   # Check if "maestroflow" target has green checkmark
   ```

4. Check Prometheus logs:
   ```bash
   docker-compose logs prometheus
   ```

**Fix:**
- Ensure `METRICS_ENABLED=true` in `.env`
- Restart app: `python3 backend/main.py`
- Reload Prometheus: `docker-compose restart prometheus`

---

### Langfuse Traces Not Appearing

**Problem:** Traces don't show up in Langfuse UI.

**Debugging Steps:**

1. Verify Langfuse is enabled:
   ```bash
   # Check .env
   LANGFUSE_ENABLED=true
   ```

2. Verify credentials are correct:
   ```bash
   # Langfuse Cloud: Get from https://cloud.langfuse.io/settings
   LANGFUSE_PUBLIC_KEY=pk_...
   LANGFUSE_SECRET_KEY=sk_...
   ```

3. Check application logs for Langfuse errors:
   ```bash
   # Look for "Langfuse" in logs
   python3 backend/main.py 2>&1 | grep -i langfuse
   ```

4. Test network connectivity:
   ```bash
   curl https://cloud.langfuse.io/api/health
   ```

5. Check async trace buffer in logs:
   ```bash
   # Should see "Flushed X traces to Langfuse" on shutdown
   ```

**Fix:**
- Double-check credentials in Langfuse Cloud settings
- Reduce `LANGFUSE_SAMPLE_RATE` if quota exceeded: `LANGFUSE_SAMPLE_RATE=0.1`
- Ensure firewall allows outbound HTTPS to cloud.langfuse.io

---

### High Memory Growth

**Problem:** Memory usage increases linearly, suggesting a memory leak.

**Debugging Steps:**

1. Check memory threshold alert in health endpoint:
   ```bash
   curl http://localhost:8000/health?verbose=true
   ```

2. Monitor memory trend:
   ```bash
   # In Prometheus, query:
   process_memory_usage_bytes
   # Check if growth rate exceeds threshold
   ```

3. Possible causes:
   - **Unbounded metric label cardinality** — Too many unique label combinations
   - **Langfuse trace buffering** — Unsent traces accumulating
   - **Cache memory leak** — Cache not evicting old entries

**Fix:**
- For metric cardinality: Normalize labels (e.g., group unknown endpoints as "OTHER")
- For Langfuse: Reduce `LANGFUSE_SAMPLE_RATE` or increase `LANGFUSE_TIMEOUT_SECONDS`
- For cache: Implement cache TTL and eviction policies

---

### Health Endpoint is Slow

**Problem:** `/health` takes > 100ms to respond.

**Debugging Steps:**

1. Check which health check is slow:
   ```bash
   curl http://localhost:8000/health?verbose=true
   ```

2. Likely culprits:
   - **Database check** — Slow query or connection timeout
   - **Memory check** — Expensive psutil call (rare)

**Fix:**
- Add database query index: `CREATE INDEX idx_health_check ON table(id)`
- Implement health check cache (only check every N seconds)
- Skip database check in `/health/live` (for liveness probes)

---

## Common Patterns

### Recording Custom Metrics

```python
from src.observability import get_metrics

metrics = get_metrics()

# Increment a counter
metrics.http_requests_total.labels(
    method="POST",
    endpoint="/approvals",
    status=200
).inc()

# Set a gauge (current value)
active_users = 150
metrics.active_users.set(active_users)

# Record a histogram value (latency, duration, size)
query_time_seconds = 0.045
metrics.db_query_duration_seconds.labels(
    query_type="SELECT"
).observe(query_time_seconds)
```

### Tracing Async Tasks

```python
from src.observability.context import get_request_context
from src.observability.task_tracing import trace_task

ctx = get_request_context()

async def background_task():
    # Manually set trace context for async task
    await trace_task(
        name="send_email",
        trace_id=ctx.trace_id,
        user_id=ctx.user_id,
    )
```

### Recording Cache Metrics

```python
from src.observability import get_metrics

metrics = get_metrics()

# On cache hit
if key in cache:
    metrics.record_cache_hit(cache_name='user_cache')
else:
    # On cache miss
    metrics.record_cache_miss(cache_name='user_cache')
    value = fetch_from_db(key)
    cache[key] = value
```

### Recording Queue Operations

```python
from src.observability import get_metrics

metrics = get_metrics()

# Update queue depth
queue_length = len(approval_queue)
metrics.record_queue_depth(queue_name='approvals', depth=queue_length)

# Record processing latency
with metrics.time_queue_processing(queue_name='approvals'):
    item = await queue.dequeue()
    await process_item(item)
```

---

## Performance Impact

Observability overhead is minimal:

| Component | Overhead | Notes |
|-----------|----------|-------|
| Metric recording | < 1ms per operation | Prometheus client is optimized |
| Middleware (request tracking) | 0.5-1ms per request | Timing adds minimal overhead |
| Memory tracking | 1-2ms per check | Background task runs every 60s |
| Langfuse tracing | Async (non-blocking) | Traces sent in background |
| **Total** | **< 5% latency increase** | **< 10% memory increase** |

For production, verify overhead with baseline testing:

```bash
# Run performance baseline before/after observability enabled
# See docs/PERFORMANCE_BASELINE.md
```

---

## Next Steps

1. **Set up dashboards** — Import pre-built Grafana dashboards
2. **Configure alerts** — Wire AlertManager to Slack/PagerDuty
3. **Define SLOs** — Set Service Level Objectives based on metrics
4. **Tune thresholds** — Adjust alert thresholds after 1-2 weeks of data
5. **Enable advanced monitoring** — Phase 3 features for fine-grained insights

---

## Reference

- **Prometheus Docs:** https://prometheus.io/docs/
- **Grafana Docs:** https://grafana.com/docs/
- **Langfuse Docs:** https://langfuse.com/docs
- **Python Prometheus Client:** https://github.com/prometheus/client_python
