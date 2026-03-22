---
type: reference
title: Observability Troubleshooting Guide
created: 2026-03-22
tags:
  - troubleshooting
  - observability
  - debugging
  - operations
related:
  - "[[OBSERVABILITY]]"
  - "[[ALERT_RUNBOOKS]]"
---

# Observability Troubleshooting Guide

## Overview

This guide addresses common issues when deploying, configuring, and operating the MaestroFlow observability system. Each issue includes the likely cause, diagnostic steps, and solutions.

---

## Metrics Not Appearing in Prometheus

### Symptoms
- Prometheus targets page shows "DOWN" for maestroflow job
- No metrics visible in Prometheus query interface
- `/metrics` endpoint returns 500 or timeout

### Diagnosis

```bash
# Check if /metrics endpoint is accessible
curl -v http://localhost:8000/metrics

# Check Prometheus configuration
cat monitoring/prometheus/prometheus.yml | grep -A 10 "maestroflow"

# Check Prometheus logs
docker logs maestroflow-prometheus-1

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Check metrics being generated
curl http://localhost:8000/metrics | head -20
```

### Solutions

#### 1. Prometheus Not Scraping the Endpoint

**Cause:** Prometheus configuration incorrect or FastAPI app not running

**Fix:**
```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'maestroflow'
    static_configs:
      - targets: ['localhost:8000']  # Ensure this matches your app host:port
    metrics_path: '/metrics'          # Ensure correct endpoint
```

**Verify:**
```bash
# Check Docker networking
docker network ls
docker network inspect maestroflow_default

# Test from inside container
docker exec maestroflow-prometheus-1 curl -v http://fastapi:8000/metrics

# Restart Prometheus with new config
docker-compose restart prometheus
```

#### 2. FastAPI App Not Generating Metrics

**Cause:** Metrics not initialized or middleware not added

**Fix:**
```python
# backend/main.py
from src.observability.middleware import MetricsMiddleware

app = FastAPI()

# Add middleware EARLY (before other middleware)
app.add_middleware(MetricsMiddleware)
```

**Verify:**
```python
# Check in Python shell
from src.observability.metrics import get_metrics
metrics = get_metrics()
print(metrics.http_requests_total)  # Should not raise
```

#### 3. Metrics Path Incorrect

**Cause:** Metrics exposed on wrong path

**Fix:**
```python
# backend/src/routers/health.py
@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    from src.observability.metrics import get_registry
    registry = get_registry()
    return Response(
        generate_latest(registry),
        media_type="text/plain; version=0.0.4"
    )
```

---

## Langfuse Traces Not Appearing

### Symptoms
- Langfuse dashboard shows no traces
- No errors in FastAPI logs
- `/metrics` shows `langfuse_traces_sent_total` not incrementing

### Diagnosis

```bash
# Check Langfuse configuration
curl -s http://localhost:8000/health | jq '.observability'

# Check if Langfuse client initialized
docker logs maestroflow-fastapi-1 | grep -i langfuse

# Test Langfuse API connectivity
curl -H "Authorization: Bearer ${LANGFUSE_SECRET_KEY}" \
  https://cloud.langfuse.com/api/trace

# Check network connectivity
curl -I https://cloud.langfuse.com

# Check error rate in Prometheus
curl 'http://localhost:9090/api/v1/query?query=langfuse_errors_total'
```

### Solutions

#### 1. Langfuse Credentials Invalid

**Cause:** Wrong API key or secret key

**Fix:**
```bash
# Verify credentials in .env
cat backend/.env | grep LANGFUSE

# Get correct credentials
# 1. Login to https://cloud.langfuse.com
# 2. Go to Settings → API Keys
# 3. Copy Public Key and Secret Key
# 4. Update backend/.env

# Verify connection
export LANGFUSE_PUBLIC_KEY="pk-xxx"
export LANGFUSE_SECRET_KEY="sk-xxx"

python3 << 'EOF'
from src.observability.langfuse_client import LangfuseClient
client = LangfuseClient()
print("✓ Connected to Langfuse")
EOF
```

#### 2. Network Unreachable

**Cause:** Firewall blocking langfuse.com, proxy issues, or incorrect host

**Fix:**
```bash
# Check network connectivity
ping cloud.langfuse.com
curl -I https://cloud.langfuse.com

# Check Docker container network
docker exec maestroflow-fastapi-1 curl -I https://cloud.langfuse.com

# Check proxy settings (if behind proxy)
export HTTP_PROXY="http://proxy:8080"
export HTTPS_PROXY="http://proxy:8080"

# For self-hosted Langfuse, verify URL
export LANGFUSE_HOST="http://langfuse:3000"  # Internal Docker URL
```

#### 3. Langfuse Disabled in Config

**Cause:** `LANGFUSE_ENABLED=false` in environment

**Fix:**
```bash
# Enable Langfuse
export LANGFUSE_ENABLED=true

# Restart app
docker-compose restart fastapi

# Verify enabled
curl http://localhost:8000/health | jq '.observability.langfuse_enabled'
```

#### 4. Sample Rate Too Low

**Cause:** `LANGFUSE_SAMPLE_RATE=0.1` (10%) - only samples 10% of requests

**Fix:**
```bash
# Increase sample rate for testing
export LANGFUSE_SAMPLE_RATE=1.0  # 100% sampling

# Restart and make request
docker-compose restart fastapi
curl http://localhost:8000/health

# Check Langfuse dashboard
# Should see trace within 10 seconds
```

---

## High Memory Growth

### Symptoms
- Memory usage continuously increasing
- RSS grows by > 1 MB/min
- Eventually hits OOM and process killed

### Diagnosis

```bash
# Check memory trend
docker stats maestroflow-fastapi-1

# Check memory usage over time
python3 << 'EOF'
import psutil
import time
process = psutil.Process(pid)  # Get app PID
for _ in range(60):
    mem = process.memory_info().rss / 1024 / 1024
    print(f"{mem:.1f} MB")
    time.sleep(1)
EOF

# Check for memory leaks in metrics
curl http://localhost:8000/metrics | grep process_resident_memory_bytes

# Check Prometheus for memory trend
# Query: rate(process_resident_memory_bytes[5m])
```

### Solutions

#### 1. Metric Cardinality Explosion

**Cause:** High-cardinality labels (e.g., unique user_id as label)

**Fix:**
```python
# DON'T do this (high cardinality)
http_requests_total.labels(user_id="user_123").inc()  # ❌ 1000s of unique labels

# DO this instead (low cardinality)
http_requests_total.labels(endpoint="/api/chat", status="200").inc()  # ✅ ~50 total combinations

# Limit labels to bounded sets
ALLOWED_LABELS = ["GET", "POST", "PUT", "DELETE"]
```

**Verify:**
```promql
# In Prometheus, check series count
count(http_requests_total)

# Should be < 1000 for healthy system
# If > 10000, likely cardinality explosion
```

#### 2. Langfuse Trace Buffer Not Flushing

**Cause:** Traces buffered in memory, not sent to Langfuse

**Fix:**
```python
# In main.py, ensure flush on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    
    # Shutdown: flush traces
    from src.observability.langfuse_client import flush_traces
    flush_traces()
```

**Verify:**
```bash
# Check Langfuse error rate
curl 'http://localhost:9090/api/v1/query?query=langfuse_errors_total'

# If errors high, traces not being sent
# Check Langfuse network connectivity
```

#### 3. Request Context Not Cleared

**Cause:** Context variables accumulating in memory

**Fix:**
```python
# Ensure context is reset after request
from src.observability.request_context import clear_request_context

@app.middleware("http")
async def clear_context(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    finally:
        clear_request_context()  # Always clear
```

---

## Health Endpoint Slow (> 100ms)

### Symptoms
- `GET /health` takes 500ms+
- Health check timeout errors in logs
- Readiness probe failing in Kubernetes

### Diagnosis

```bash
# Measure health endpoint latency
time curl http://localhost:8000/health

# Check which health check is slow
curl http://localhost:8000/health?verbose=true | jq '.'

# Check database latency
curl http://localhost:8000/health?verbose=true | jq '.database'

# Check Redis latency
curl http://localhost:8000/health?verbose=true | jq '.cache'

# Profile the health check
python3 << 'EOF'
import time
from src.routers.health import check_database

start = time.time()
result = check_database()
elapsed = (time.time() - start) * 1000
print(f"Database check: {elapsed:.1f}ms")
print(f"Result: {result}")
EOF
```

### Solutions

#### 1. Database Check Slow

**Cause:** Database query slow or connection pool exhausted

**Fix:**
```python
# Option 1: Add database index
# If querying by user_id in health check:
# CREATE INDEX idx_health_check ON queries(created_at DESC) WHERE status='active';

# Option 2: Cache health check result
from src.observability.health_aggregator import HealthAggregator

aggregator = HealthAggregator(cache_ttl_seconds=30)

@router.get("/health")
async def health():
    # Returns cached result for 30 seconds
    return aggregator.aggregate()

# Option 3: Make check async
async def check_database():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _check_database_sync)
```

#### 2. Health Check Scope Too Broad

**Cause:** Checking too many external services

**Fix:**
```python
# Separate readiness from liveness
@router.get("/health/ready")
async def ready():
    """Only critical checks (database, cache)"""
    return {
        "status": "ready" if (check_db() and check_cache()) else "not_ready"
    }

@router.get("/health/live")
async def live():
    """Quick check (always 200ms)"""
    return {"status": "healthy"}  # No external checks

@router.get("/health")
async def health():
    """Informational checks (DB, queue, memory)"""
    return aggregator.aggregate()
```

#### 3. Connection Pool Exhausted

**Cause:** All database connections in use

**Fix:**
```python
# Increase pool size
export DB_POOL_MAX_SIZE=20  # Default might be 5

# Or use connection pooling middleware
from sqlalchemy.pool import QueuePool
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
)
```

---

## Missing Context in Langfuse Traces

### Symptoms
- Langfuse traces don't have request_id or trace_id
- Missing metadata (user_id, endpoint, method)
- Traces don't correlate across services

### Diagnosis

```bash
# Check what context is being captured
# Make a request and check middleware output
curl -v http://localhost:8000/health

# Check if context is initialized
python3 << 'EOF'
from src.observability.request_context import get_request_context
ctx = get_request_context()
print(f"trace_id: {ctx.trace_id}")
print(f"request_id: {ctx.request_id}")
print(f"user_id: {ctx.user_id}")
EOF

# Check Langfuse dashboard for trace metadata
# Go to trace details → check "metadata" tab
```

### Solutions

#### 1. Middleware Not Running Early Enough

**Cause:** Middleware added after other middleware that might be removing context

**Fix:**
```python
# In main.py, add MetricsMiddleware FIRST
app = FastAPI()

# Add observability middleware BEFORE everything else
app.add_middleware(MetricsMiddleware)

# Then add other middleware
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(AuthMiddleware, ...)
```

#### 2. Async Context Not Propagated

**Cause:** Using threading instead of async context variables

**Fix:**
```python
# Use contextvars for async-safe context
from contextvars import ContextVar

_trace_id_var: ContextVar[str] = ContextVar('trace_id', default=None)

def get_trace_id() -> str:
    return _trace_id_var.get()

def set_trace_id(trace_id: str):
    _trace_id_var.set(trace_id)

# NOT thread-local storage (which doesn't work with async)
# ❌ threading.local() won't work
# ✅ contextvars.ContextVar() will work
```

#### 3. Context Cleared Too Early

**Cause:** Context cleared before Langfuse can capture it

**Fix:**
```python
# Ensure context is available when trace is sent
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
    
    # Set context at start of request
    set_request_context(trace_id=trace_id)
    
    try:
        response = await call_next(request)
        return response
    finally:
        # Clear context AFTER trace is sent (Langfuse flushes async)
        await asyncio.sleep(0.1)  # Give trace time to queue
        clear_request_context()
```

---

## Prometheus Disk Usage Too High

### Symptoms
- `/var/lib/prometheus` grows rapidly
- Prometheus query slow or unresponsive
- "disk full" errors in logs

### Diagnosis

```bash
# Check disk usage
du -sh /var/lib/prometheus/*

# Check retention settings
grep retention monitoring/prometheus/prometheus.yml

# Check number of time series
curl http://localhost:9090/api/v1/query?query='count(up)'

# Check metric cardinality
curl 'http://localhost:9090/api/v1/query?query=count({__name__=~".+"})' 
```

### Solutions

#### 1. Retention Policy Too Long

**Cause:** Default retention might be 15 days, too long

**Fix:**
```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  retention: 7d  # Reduce from 15d to 7d
```

Restart Prometheus:
```bash
docker-compose restart prometheus
```

#### 2. High Cardinality Metrics

**Cause:** Metrics with too many labels (see earlier section)

**Fix:**
```python
# Remove high-cardinality labels
# ❌ BAD
cache_hits_total.labels(user_id="123", endpoint="/api", status="200").inc()

# ✅ GOOD
cache_hits_total.labels(endpoint="/api", status="200").inc()
```

#### 3. Disk Full - Cleanup

**Cause:** Disk completely full, Prometheus can't write

**Fix:**
```bash
# Stop Prometheus
docker-compose stop prometheus

# Remove old data (careful!)
rm -rf /var/lib/prometheus/wal
rm -rf /var/lib/prometheus/snapshots

# Or delete specific days
find /var/lib/prometheus -type d -mtime +7 -exec rm -rf {} \;

# Restart
docker-compose up prometheus
```

---

## Grafana Not Updating Dashboards

### Symptoms
- Dashboard panels show old data
- Refresh button doesn't update
- Manual query in Prometheus works, but Grafana doesn't

### Diagnosis

```bash
# Check Prometheus datasource connection
# In Grafana: Configuration → Data Sources → Prometheus → Test

# Check Prometheus response time
curl -I http://localhost:9090/api/v1/query?query=up

# Check Grafana logs
docker logs maestroflow-grafana-1 | tail -50

# Check panel refresh interval
# In Grafana: Open panel → Edit → Refresh interval
```

### Solutions

#### 1. Prometheus Datasource Not Connected

**Cause:** Grafana can't reach Prometheus

**Fix:**
```yaml
# monitoring/grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
dataSources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090  # Internal Docker DNS
    access: proxy
    isDefault: true
```

Restart Grafana:
```bash
docker-compose restart grafana
```

#### 2. Panel Query Error

**Cause:** Metric name changed or typo in PromQL

**Fix:**
```promql
# Go to panel → Edit → Check query
# Common errors:
# - http_requests_total (wrong)
# + http_request_duration_seconds (correct)

# Test in Prometheus query interface
# http://localhost:9090 → Graphs → paste query → Execute
```

#### 3. Auto-refresh Disabled

**Cause:** Dashboard refresh set to "Off"

**Fix:**
```
In Grafana:
1. Dashboard → Top right "Auto refresh" dropdown
2. Select "5s" or preferred interval
3. Click refresh icon or wait for auto-refresh
```

---

## Common Commands & Debug Tips

### Checking Service Health

```bash
# Check all services
docker-compose ps

# Check specific service logs
docker logs maestroflow-fastapi-1 -f
docker logs maestroflow-prometheus-1 -f
docker logs maestroflow-grafana-1 -f

# Check Docker networking
docker network inspect maestroflow_default
```

### Prometheus Queries for Debugging

```promql
# Check scrape success rate
rate(prometheus_tsdb_symbol_table_size_bytes[5m])

# Check maestroflow metrics volume
rate(prometheus_tsdb_metric_chunks_created_total{job="maestroflow"}[5m])

# Check memory pressure
process_resident_memory_bytes{job="prometheus"}

# Check query latency
histogram_quantile(0.95, prometheus_http_request_duration_seconds_bucket)

# Check errors
rate(prometheus_http_requests_total{code!="200"}[5m])
```

### FastAPI Debug Mode

```python
# In main.py, add debug logging
logging.basicConfig(level=logging.DEBUG)

# Check metrics initialization
python3 << 'EOF'
from src.observability.metrics import get_metrics
metrics = get_metrics()
print(f"HTTP requests: {metrics.http_requests_total}")
print(f"Cache hits: {metrics.cache_hits_total}")
EOF
```

### Network Testing

```bash
# From inside container
docker exec maestroflow-fastapi-1 bash

# Inside container, test connectivity
curl http://prometheus:9090/api/v1/targets
curl https://cloud.langfuse.com/api/trace

# Check DNS
nslookup prometheus
nslookup cloud.langfuse.com
```

---

## When All Else Fails

### Full System Reset

```bash
# Stop everything
docker-compose down

# Clean volumes
docker volume prune

# Remove old data
rm -rf /var/lib/prometheus
rm -rf /var/lib/grafana

# Restart fresh
docker-compose up -d

# Wait for services
sleep 10

# Verify
docker-compose ps
curl http://localhost:8000/health
```

### Escalation Checklist

- [ ] Check application logs for errors
- [ ] Verify environment variables are set
- [ ] Test network connectivity between services
- [ ] Check disk space and memory availability
- [ ] Review Prometheus/Grafana configuration files
- [ ] Verify API credentials (Langfuse, etc.)
- [ ] Check firewall rules
- [ ] Review Docker daemon logs
- [ ] Restart individual services
- [ ] Full system reset (last resort)

---

## Getting Help

When reporting issues, include:

1. **Error message** (full text, not just first line)
2. **Environment info** (OS, Docker version, Python version)
3. **Steps to reproduce** (exact commands)
4. **Logs** (from all relevant services):
   ```bash
   docker-compose logs > logs.txt
   ```
5. **Configuration** (masking secrets):
   ```bash
   cat backend/.env | grep -v SECRET
   ```
6. **Metrics/Traces** (if available):
   ```bash
   curl http://localhost:8000/metrics > metrics.txt
   ```
