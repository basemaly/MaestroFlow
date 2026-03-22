---
type: reference
title: MaestroFlow Metrics Reference
created: 2026-03-21
tags:
  - metrics
  - prometheus
  - monitoring
  - reference
---

# MaestroFlow Metrics Reference

Complete list of all Prometheus metrics exposed by MaestroFlow application.

## Metric Naming Convention

All metrics follow the pattern: `{component}_{metric_name}_{unit}`

- **component:** What system the metric measures (http, db, cache, queue, etc.)
- **metric_name:** What is being measured (latency, count, depth, ratio, etc.)
- **unit:** The unit of measurement (seconds, bytes, total, ratio, percent, etc.)

### Examples

- `http_request_duration_seconds` — HTTP request latency measured in seconds
- `db_query_duration_seconds` — Database query duration in seconds
- `queue_depth` — Current queue depth (unitless count)
- `process_memory_usage_bytes` — Process memory in bytes

---

## HTTP Metrics

Track request/response performance for FastAPI endpoints.

### http_request_duration_seconds (Histogram)

**Type:** Histogram  
**Labels:** `endpoint`, `method`, `status`  
**Unit:** Seconds  
**Description:** Time taken to process HTTP request

**Example:**
```
http_request_duration_seconds_bucket{endpoint="/approvals",method="GET",le="0.005"} 10
http_request_duration_seconds_bucket{endpoint="/approvals",method="GET",le="0.01"} 25
http_request_duration_seconds_bucket{endpoint="/approvals",method="GET",le="0.025"} 150
http_request_duration_seconds_count{endpoint="/approvals",method="GET"} 500
http_request_duration_seconds_sum{endpoint="/approvals",method="GET"} 12.5
```

**Query Examples:**
```
# Average latency per endpoint
avg by (endpoint) (http_request_duration_seconds_sum / http_request_duration_seconds_count)

# p95 latency
histogram_quantile(0.95, http_request_duration_seconds)

# p99 latency for specific endpoint
histogram_quantile(0.99, http_request_duration_seconds{endpoint="/approvals"})
```

**Typical Value:** 0.001 - 0.5 seconds

**Alert Threshold:** p95 > 1 second, p99 > 5 seconds

---

### http_requests_total (Counter)

**Type:** Counter  
**Labels:** `endpoint`, `method`, `status`  
**Unit:** Total count  
**Description:** Total number of HTTP requests processed

**Example:**
```
http_requests_total{endpoint="/approvals",method="GET",status="200"} 1000
http_requests_total{endpoint="/approvals",method="GET",status="500"} 5
http_requests_total{endpoint="/api/submit",method="POST",status="201"} 500
```

**Query Examples:**
```
# Requests per second
rate(http_requests_total[5m])

# Error rate (5xx)
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Request rate by endpoint
rate(http_requests_total[5m]) by (endpoint)
```

**Typical Value:** Depends on traffic (100 - 10,000+ total)

**Alert Threshold:** 5xx error rate > 5%

---

## Database Metrics

Monitor connection pool and query performance.

### db_connections_active (Gauge)

**Type:** Gauge  
**Labels:** `pool_name`  
**Unit:** Count  
**Description:** Current number of active database connections

**Example:**
```
db_connections_active{pool_name="main"} 5
```

**Query Examples:**
```
# Connection pool utilization
db_connections_active / db_pool_max_size

# Alert if pool running low
(db_pool_max_size - db_connections_active) < 2
```

**Typical Value:** 0 - 10 (depending on pool size)

**Alert Threshold:** Pool utilization > 80%

---

### db_connections_total (Counter)

**Type:** Counter  
**Labels:** `pool_name`  
**Unit:** Total count  
**Description:** Total connections created since app started

**Example:**
```
db_connections_total{pool_name="main"} 1500
```

**Typical Value:** Increases over time (hundreds to thousands)

---

### db_connections_reused (Counter)

**Type:** Counter  
**Labels:** `pool_name`  
**Unit:** Total count  
**Description:** Total connections reused from pool

**Example:**
```
db_connections_reused{pool_name="main"} 95000
```

**Query Examples:**
```
# Connection reuse ratio
db_connections_reused / (db_connections_total + db_connections_reused)
```

**Typical Value:** High number (reuse is more efficient)

---

### db_connection_wait_seconds (Histogram)

**Type:** Histogram  
**Labels:** `pool_name`  
**Unit:** Seconds  
**Description:** Time spent waiting to acquire connection from pool

**Example:**
```
db_connection_wait_seconds_bucket{pool_name="main",le="0.001"} 5000
db_connection_wait_seconds_bucket{pool_name="main",le="0.01"} 4990
db_connection_wait_seconds_count{pool_name="main"} 4990
```

**Query Examples:**
```
# p95 connection wait time
histogram_quantile(0.95, db_connection_wait_seconds)

# Average connection wait
db_connection_wait_seconds_sum / db_connection_wait_seconds_count
```

**Typical Value:** 0.0001 - 0.01 seconds

**Alert Threshold:** p95 > 0.5 seconds

---

### db_query_duration_seconds (Histogram)

**Type:** Histogram  
**Labels:** `query_type` (SELECT, INSERT, UPDATE, DELETE)  
**Unit:** Seconds  
**Description:** Time taken to execute database query

**Example:**
```
db_query_duration_seconds_bucket{query_type="SELECT",le="0.001"} 1000
db_query_duration_seconds_bucket{query_type="SELECT",le="0.01"} 950
db_query_duration_seconds_count{query_type="SELECT"} 950
```

**Query Examples:**
```
# Average query time by type
avg by (query_type) (rate(db_query_duration_seconds_sum[5m]) / rate(db_query_duration_seconds_count[5m]))

# Slow query detection (p99 > 1 second)
histogram_quantile(0.99, db_query_duration_seconds) > 1
```

**Typical Value:** 0.001 - 0.1 seconds

**Alert Threshold:** p99 > 1 second

---

## Queue Metrics

Monitor task queues and processing latency.

### queue_depth (Gauge)

**Type:** Gauge  
**Labels:** `queue_name`  
**Unit:** Count  
**Description:** Current number of items in queue

**Example:**
```
queue_depth{queue_name="approvals"} 42
queue_depth{queue_name="notifications"} 5
```

**Query Examples:**
```
# Queue utilization (assuming max 1000)
queue_depth / 1000

# High queue depth alert
queue_depth > 800
```

**Typical Value:** 0 - 100 (lower is better)

**Alert Threshold:** > 80% of capacity

---

### queue_processed_total (Counter)

**Type:** Counter  
**Labels:** `queue_name`  
**Unit:** Total count  
**Description:** Total items processed from queue since app started

**Example:**
```
queue_processed_total{queue_name="approvals"} 50000
```

**Typical Value:** High number (thousands)

---

### queue_processing_latency_seconds (Histogram)

**Type:** Histogram  
**Labels:** `queue_name`  
**Unit:** Seconds  
**Description:** End-to-end time from queue entry to completion

**Example:**
```
queue_processing_latency_seconds_bucket{queue_name="approvals",le="1"} 100
queue_processing_latency_seconds_bucket{queue_name="approvals",le="10"} 950
queue_processing_latency_seconds_count{queue_name="approvals"} 950
```

**Query Examples:**
```
# p95 queue processing latency (SLA)
histogram_quantile(0.95, queue_processing_latency_seconds)

# Alert if SLA breached (> 10 seconds)
histogram_quantile(0.95, queue_processing_latency_seconds) > 10
```

**Typical Value:** 0.1 - 5 seconds

**Alert Threshold:** p95 > 10 seconds

---

## Cache Metrics

Monitor caching effectiveness.

### cache_hits_total (Counter)

**Type:** Counter  
**Labels:** `cache_name`  
**Unit:** Total count  
**Description:** Total cache hits since app started

**Example:**
```
cache_hits_total{cache_name="user_cache"} 95000
cache_hits_total{cache_name="config_cache"} 10000
```

**Typical Value:** High number (thousands)

---

### cache_misses_total (Counter)

**Type:** Counter  
**Labels:** `cache_name`  
**Unit:** Total count  
**Description:** Total cache misses since app started

**Example:**
```
cache_misses_total{cache_name="user_cache"} 5000
```

**Typical Value:** Lower than hits (hundreds to thousands)

---

### cache_hit_ratio (Gauge)

**Type:** Gauge  
**Labels:** `cache_name`  
**Unit:** Ratio (0.0 - 1.0)  
**Description:** Proportion of requests that hit cache

**Example:**
```
cache_hit_ratio{cache_name="user_cache"} 0.95
cache_hit_ratio{cache_name="config_cache"} 0.98
```

**Query Examples:**
```
# Cache efficiency
cache_hit_ratio by (cache_name)

# Alert if hit ratio drops below 50%
cache_hit_ratio < 0.5
```

**Typical Value:** 0.5 - 0.99 (higher is better)

**Alert Threshold:** < 20% (indicates cache ineffectiveness)

---

## WebSocket Metrics

Monitor real-time connections and messaging.

### websocket_connections_active (Gauge)

**Type:** Gauge  
**Unit:** Count  
**Description:** Current active WebSocket connections

**Example:**
```
websocket_connections_active 42
```

**Typical Value:** 0 - 1000+ (depends on traffic)

---

### websocket_connections_total (Counter)

**Type:** Counter  
**Unit:** Total count  
**Description:** Total WebSocket connections since app started

**Example:**
```
websocket_connections_total 50000
```

**Typical Value:** High number (thousands)

---

### websocket_messages_sent_total (Counter)

**Type:** Counter  
**Unit:** Total count  
**Description:** Total messages sent to clients

**Example:**
```
websocket_messages_sent_total 500000
```

**Typical Value:** Very high (millions possible)

---

### websocket_messages_received_total (Counter)

**Type:** Counter  
**Unit:** Total count  
**Description:** Total messages received from clients

**Example:**
```
websocket_messages_received_total 450000
```

**Typical Value:** Similar to sent messages

---

### websocket_connection_duration_seconds (Histogram)

**Type:** Histogram  
**Unit:** Seconds  
**Description:** How long WebSocket connections stay open

**Example:**
```
websocket_connection_duration_seconds_bucket{le="60"} 100
websocket_connection_duration_seconds_bucket{le="3600"} 500
```

**Query Examples:**
```
# Average connection duration
websocket_connection_duration_seconds_sum / websocket_connection_duration_seconds_count

# p95 connection lifetime
histogram_quantile(0.95, websocket_connection_duration_seconds)
```

**Typical Value:** 60 - 3600 seconds

---

## Memory Metrics

Monitor application memory usage.

### process_memory_usage_bytes (Gauge)

**Type:** Gauge  
**Labels:** None  
**Unit:** Bytes  
**Description:** Current resident set size (RSS) memory used by process

**Example:**
```
process_memory_usage_bytes 104857600  # 100 MB
```

**Query Examples:**
```
# Convert to MB
process_memory_usage_bytes / 1024 / 1024

# Memory growth rate (MB/minute)
rate(process_memory_usage_bytes[5m]) / 1024 / 1024

# Alert if memory > 1GB
process_memory_usage_bytes > 1073741824
```

**Typical Value:** 50 - 500 MB (depends on data structures)

**Alert Threshold:** 
- Warning: > 512 MB
- Critical: > 1024 MB (configurable)

---

## LLM Metrics

Track LLM API calls and costs.

### llm_calls_total (Counter)

**Type:** Counter  
**Labels:** `model`, `status` (success, error)  
**Unit:** Total count  
**Description:** Total LLM API calls made

**Example:**
```
llm_calls_total{model="gpt-4",status="success"} 1000
llm_calls_total{model="gpt-4",status="error"} 5
```

**Typical Value:** Hundreds to thousands

---

### llm_tokens_used_total (Counter)

**Type:** Counter  
**Labels:** `model`, `token_type` (prompt, completion)  
**Unit:** Total tokens  
**Description:** Total tokens consumed (prompt + completion)

**Example:**
```
llm_tokens_used_total{model="gpt-4",token_type="prompt"} 50000
llm_tokens_used_total{model="gpt-4",token_type="completion"} 25000
```

**Query Examples:**
```
# Total tokens used
llm_tokens_used_total

# Cost calculation (assuming $0.03 per 1K tokens)
(llm_tokens_used_total / 1000) * 0.03
```

**Typical Value:** Tens of thousands

---

### llm_cost_usd_total (Counter)

**Type:** Counter  
**Labels:** `model`  
**Unit:** USD (dollars)  
**Description:** Total cost of LLM API calls

**Example:**
```
llm_cost_usd_total{model="gpt-4"} 150.25
```

**Query Examples:**
```
# Cost per hour
rate(llm_cost_usd_total[1h])

# Cost per model
llm_cost_usd_total by (model)

# Alert if cost/hour > $100
rate(llm_cost_usd_total[1h]) > 100
```

**Typical Value:** Dollars (0 - thousands depending on usage)

**Alert Threshold:** > $100/hour

---

### llm_request_duration_seconds (Histogram)

**Type:** Histogram  
**Labels:** `model`  
**Unit:** Seconds  
**Description:** Time to complete LLM API request

**Example:**
```
llm_request_duration_seconds_bucket{model="gpt-4",le="1"} 0
llm_request_duration_seconds_bucket{model="gpt-4",le="10"} 500
```

**Typical Value:** 1 - 30 seconds

**Alert Threshold:** p95 > 30 seconds

---

## Health Check Metrics

System health and availability.

### up (Gauge)

**Type:** Gauge  
**Labels:** `job` (prometheus, maestroflow)  
**Unit:** 0 or 1  
**Description:** Whether target is up and responding

**Example:**
```
up{job="maestroflow"} 1
up{job="prometheus"} 1
```

**Query Examples:**
```
# Alert if maestroflow is down
up{job="maestroflow"} == 0
```

---

## Querying Metrics

### Common PromQL Queries

**1. Average latency last 5 minutes**
```
avg(rate(http_request_duration_seconds_sum[5m])) / avg(rate(http_request_duration_seconds_count[5m]))
```

**2. Request rate by status code**
```
rate(http_requests_total[5m]) by (status)
```

**3. Error rate (5xx)**
```
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])
```

**4. Cache effectiveness**
```
cache_hits_total / (cache_hits_total + cache_misses_total)
```

**5. Database connection pool utilization**
```
db_connections_active / 10  # Assuming max pool size is 10
```

**6. LLM costs per day**
```
increase(llm_cost_usd_total[1d])
```

---

## Recording Rules

Prometheus recording rules pre-compute commonly used queries for better performance.

Common recording rules to implement:

```yaml
# Compute request rates
- record: http:requests:rate5m
  expr: rate(http_requests_total[5m])

# Compute error rates
- record: http:errors:rate5m
  expr: rate(http_requests_total{status=~"5.."}[5m])

# Compute cache hit ratio
- record: cache:hit_ratio:instant
  expr: cache_hits_total / (cache_hits_total + cache_misses_total)

# Compute LLM costs per hour
- record: llm:cost:rate1h
  expr: rate(llm_cost_usd_total[1h])
```

---

## Metric Cardinality

Be aware of high-cardinality metrics that can cause performance issues:

| Metric | Labels | Risk | Mitigation |
|--------|--------|------|-----------|
| `http_request_duration_seconds` | `endpoint`, `method`, `status` | HIGH (many unique endpoints) | Group unknown endpoints as "OTHER" |
| `db_query_duration_seconds` | `query_type` | LOW (fixed set: SELECT, INSERT, UPDATE, DELETE) | None needed |
| `cache_hit_ratio` | `cache_name` | LOW (fixed set of caches) | None needed |
| `llm_cost_usd_total` | `model` | MEDIUM (many models exist) | Limit to top N models |

---

## Dashboard Recommendations

Create these Grafana panels:

1. **Request Rate** — `rate(http_requests_total[5m])`
2. **Error Rate** — `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])`
3. **Latency p95** — `histogram_quantile(0.95, http_request_duration_seconds)`
4. **Cache Hit Ratio** — `cache_hit_ratio`
5. **Queue Depth** — `queue_depth`
6. **Memory Usage** — `process_memory_usage_bytes / 1024 / 1024`
7. **LLM Cost/Hour** — `rate(llm_cost_usd_total[1h])`
8. **Active Connections** — `websocket_connections_active`

---

## Further Reading

- [Prometheus Metric Types](https://prometheus.io/docs/concepts/metric_types/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Metric Naming Best Practices](https://prometheus.io/docs/practices/naming/)
