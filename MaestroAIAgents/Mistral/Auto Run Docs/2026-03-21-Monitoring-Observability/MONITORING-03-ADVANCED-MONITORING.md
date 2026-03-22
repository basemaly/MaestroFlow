# Phase 3: Advanced Observability - Memory, Cache, & Queue Monitoring

**Objective:** Implement comprehensive monitoring for memory usage, cache performance, and background queue depth/latency. Add alerting thresholds and trend analysis.

---

## 1. Memory Usage Monitoring (`backend/src/observability/memory_tracking.py`)

- [ ] Create `backend/src/observability/memory_tracking.py`
  - Import `psutil` library for process metrics
  - Create `MemoryTracker` class that periodically samples:
    - RSS (Resident Set Size) in MB
    - VMS (Virtual Memory Size) in MB
    - Percent of system memory used
    - Page faults (major/minor) if available
  - Emit Prometheus gauge: `process_memory_rss_bytes`, `process_memory_vms_bytes`, `process_memory_percent`
  - Emit counter: `process_page_faults_total` (with label: major/minor)
  - Add configurable sampling interval (default: 30 seconds)

- [ ] Create memory trend analysis
  - Store last 60 samples (60 * 30s = 30 minutes of history)
  - Calculate memory growth rate (MB/minute)
  - Detect potential memory leaks (sustained growth > 1 MB/min for > 10 minutes)
  - Emit Prometheus gauge: `process_memory_growth_rate_mb_per_minute` (could be negative)
  - Create alert: if memory exceeds `MEMORY_THRESHOLD_MB` or growth rate > threshold

- [ ] Add memory-aware health check
  - In health check endpoint: if memory > 80% of threshold, return status: "degraded"
  - If memory > threshold: return 503 Service Unavailable

- [ ] Background memory monitoring task
  - Start background thread or async task on app startup
  - Sample memory every 30 seconds
  - Log warnings if growth rate is concerning
  - Emit metrics to Prometheus

---

## 2. Cache Monitoring (`backend/src/observability/cache_tracking.py`)

- [ ] Create `backend/src/observability/cache_tracking.py`
  - Define `CacheMetrics` class for tracking hit/miss/eviction stats
  - Implement `@track_cache_operation` decorator:
    - Wraps cache.get() and cache.put() calls
    - Records cache_hits_total, cache_misses_total, cache_evictions_total
    - Calculates cache_hit_ratio gauge (updated on every operation)
    - Tracks eviction count to detect thrashing
  - Supports multiple cache types: in-memory dict, Redis, memcached, etc.

- [ ] Identify cache usage in codebase
  - Search for cache patterns: LRU, TTL-based, Redis, etc.
  - If using Redis: capture hit/miss from Redis INFO stats instead of application-level tracking
  - If using in-memory cache: apply decorator to cache operations

- [ ] Cache coherence monitoring (optional)
  - If multiple cache layers exist (local + Redis):
    - Track times when values differ between layers
    - Emit metric: `cache_coherence_mismatches_total`
    - Emit alert if mismatch ratio is high

- [ ] Cache eviction analysis
  - Capture eviction reason (TTL expired, LRU evicted, manual clear, etc.)
  - Create Prometheus counter: `cache_evictions_total` (labeled by cache_name, reason)
  - If eviction rate is very high (> 100/minute), emit warning: possible cache thrashing

- [ ] Add cache health to health check
  - Check if hit_ratio < 20%, return warning in health response
  - If hit_ratio < 5%, return degraded status

---

## 3. Queue Monitoring (`backend/src/observability/queue_tracking.py`)

- [ ] Create `backend/src/observability/queue_tracking.py`
  - Define `QueueMetrics` class for tracking queue depth, processing latency, error rate
  - Create context manager: `@track_queue_operation(queue_name, task_type)`
    - Records start time, task type, queue name
    - Increments `queue_processed_total` on completion
    - Records duration in `queue_processing_latency_seconds` histogram
    - Captures errors and increments `queue_errors_total` counter

- [ ] Queue depth monitoring
  - If using async queue (asyncio.Queue, multiprocessing.Queue, Celery):
    - Emit gauge: `queue_depth` (labeled by queue_name)
    - Sample queue size every 10 seconds
  - Emit gauge: `queue_depth_max_capacity` (if queue has max size)
  - Create alert: if queue_depth > 80% of max_capacity, emit warning

- [ ] Queue latency SLA monitoring
  - Define SLA for queue processing (e.g., 95th percentile < 5 seconds)
  - Use histogram to track latency percentiles
  - Create alert: if p95 latency > SLA threshold, emit warning
  - Track SLA compliance rate (% of tasks meeting SLA)

- [ ] Queue error tracking
  - Create counter: `queue_errors_total` (labeled by queue_name, error_type)
  - Create gauge: `queue_error_rate` (errors/minute, labeled by queue_name)
  - Emit alert: if error_rate > 5%, return degraded health

- [ ] Dead-letter queue monitoring (if applicable)
  - Track items moved to DLQ
  - Emit counter: `queue_dlq_messages_total` (labeled by queue_name)
  - Monitor DLQ depth to detect recurring failures

- [ ] Add queue health to health check
  - Check if queue depth is near capacity
  - Check if recent error rate is high
  - Return degraded status if either condition is true

---

## 4. WebSocket Connection Monitoring

- [x] Enhance WebSocket metrics (completed in Phase 1 and 3)
  - Added connection lifecycle tracking with disconnect reason logging ✓
  - Added per-endpoint metrics: websocket_connections_by_endpoint ✓
  - Added message throughput tracking: websocket_messages_per_second ✓
  - Added message size histogram: websocket_message_size_bytes ✓
  - Added error tracking by endpoint and error type ✓
  - Added disconnect reason counter for graceful/timeout/error/heartbeat_failed ✓

- [x] Connection health monitoring
  - Implemented async heartbeat mechanism with track_websocket_heartbeat() ✓
  - Added heartbeat failure tracking with max_failures threshold ✓
  - Added websocket_heartbeat_failures_total counter by endpoint ✓
  - Disconnect after 3 consecutive heartbeat failures with tracking ✓

- [x] WebSocket error tracking
  - Added websocket_errors_total counter with endpoint and error_type labels ✓
  - Exception handling in message tracing with error logging ✓
  - Full stack trace included in Langfuse traces ✓

---

## 5. Composite Health Scoring

- [x] Create `backend/src/observability/health_aggregator.py`
  - Comprehensive HealthScorer class with component evaluation ✓
  - All 5 components scored (0-100): database, queue, cache, memory, websockets ✓
  - Weighted scoring: db(40%), queue(30%), cache(15%), memory(10%), ws(5%) ✓
  - Status determination: ≥80=healthy, 60-79=degraded, <60=unhealthy ✓

- [x] Detailed health response format
  - JSON response with per-component breakdown ✓
  - Includes component scores, status, and reasons ✓
  - Overall score reflects weighted composition ✓

- [x] Thresholds and alerting rules
  - Added to `backend/src/config/observability.py`: ✓
    - DB_HEALTH_THRESHOLD_SLOW_QUERY_MS (default: 1000) ✓
    - QUEUE_HEALTH_THRESHOLD_DEPTH_PERCENT (default: 80) ✓
    - CACHE_HEALTH_THRESHOLD_HIT_RATIO_PERCENT (default: 20) ✓
    - MEMORY_HEALTH_THRESHOLD_GROWTH_RATE_MB_MIN (default: 5.0) ✓
    - WEBSOCKET_HEALTH_THRESHOLD_ERROR_RATE_PERCENT (default: 5.0) ✓

---

## 6. Alerting Rules (Prometheus AlertManager)

- [x] Create `monitoring/prometheus/alerts.yml`
  - All 8 alert rules defined with severity levels ✓
  - Memory growth rate > 5 MB/min for 10 minutes ✓
  - Cache hit ratio < 20% for 5 minutes ✓
  - Queue depth > 80% capacity for 2 minutes ✓
  - Queue processing latency p95 > 10 seconds ✓
  - WebSocket error rate > 5% for 5 minutes ✓
  - Database query latency p99 > 1 second for 5 minutes ✓
  - Uncaught exceptions > 10/minute ✓
  - All alerts include severity, component, and runbook_url labels ✓

- [x] Create runbooks for each alert
  - `docs/runbooks/high-memory-growth.md` ✓
  - `docs/runbooks/cache-thrashing.md` ✓
  - `docs/runbooks/queue-depth-high.md` ✓
  - `docs/runbooks/low-cache-hit-ratio.md` ✓
  - `docs/runbooks/queue-latency-sla.md` ✓
  - `docs/runbooks/queue-error-rate.md` ✓
  - `docs/runbooks/websocket-errors.md` ✓
  - `docs/runbooks/websocket-heartbeat.md` ✓
  - All runbooks include: description, likely causes, troubleshooting, resolution, prevention ✓

---

## 7. Metrics Export & Dashboard

- [x] Create `monitoring/prometheus/prometheus.yml`
  - Scrape job configured for application metrics endpoint ✓
  - Scrape interval: 15 seconds ✓
  - Evaluation interval for alerts: 15 seconds ✓
  - AlertManager webhook configured ✓

- [x] Create Grafana dashboard JSON
  - `monitoring/grafana/dashboards/maestroflow-observability.json` ✓
  - 9 comprehensive panels: ✓
    - Memory usage over time (RSS + VMS) ✓
    - Memory growth rate trend with thresholds ✓
    - Cache hit ratio trend with per-cache breakdown ✓
    - Queue depth gauge with color thresholds ✓
    - Queue latency percentiles (p95, p99) heatmap ✓
    - WebSocket active connections gauge ✓
    - Request error rate by endpoint (stacked bar) ✓
    - Overall system health score gauge (0-100) ✓
  - Template variables for cache_name, queue_name, time_range filters ✓
  - 30-second refresh interval, 1-hour default time range ✓

---

## 8. Tests for Advanced Monitoring

- [x] Create `backend/tests/test_memory_tracking.py`
  - Test that memory samples are collected ✓
  - Test that growth rate is calculated correctly ✓
  - Test alert triggers when threshold exceeded ✓
  - 18 comprehensive test cases covering initialization, sampling, growth rate, leak detection, and health status

- [x] Create `backend/tests/test_cache_tracking.py`
  - Test that hit/miss counters are incremented ✓
  - Test that hit_ratio gauge is updated correctly ✓
  - Test eviction tracking ✓
  - 18 comprehensive test cases covering metrics, tracker, decorator, and Prometheus integration

- [x] Create `backend/tests/test_queue_tracking.py`
  - Test that queue depth gauge is updated ✓
  - Test latency histogram records correct percentiles ✓
  - Test error rate calculation ✓
  - 20 comprehensive test cases covering metrics, context managers, async operations, and integration scenarios

- [x] Create `backend/tests/test_health_aggregator.py`
  - Test component score calculation ✓
  - Test weighted health score ✓
  - Test status assignment (healthy/degraded/unhealthy) ✓
  - 21 comprehensive test cases covering health scoring, component health, and integration scenarios

- [x] Create `backend/tests/test_websocket_monitoring.py`
  - Test WebSocket message tracing (send/receive) ✓
  - Test connection lifecycle tracing ✓
  - Test metrics recording for all operations ✓
  - 14 comprehensive test cases covering edge cases and integration scenarios

---

## Success Criteria

- ✅ Memory usage is tracked with growth rate detection
- ✅ Cache hit/miss ratios are monitored per cache instance
- ✅ Queue depth and latency are tracked with SLA monitoring
- ✅ WebSocket connection lifecycle is fully instrumented
- ✅ Composite health score reflects overall system health
- ✅ Alert rules are defined for all critical metrics
- ✅ Grafana dashboard displays all key metrics
- ✅ All tests pass

---

## Notes

- **Sampling intervals:** Vary by metric (memory: 30s, queue: 10s, cache: on-operation)
- **Storage:** Prometheus stores metrics for 15 days by default; adjust if needed
- **Dashboard refresh:** 30 seconds is good for operational dashboards; faster for incident response
- **Alerting:** Use AlertManager to route alerts to Slack, PagerDuty, etc. (not covered in this phase)

---

## Related Issues Addressed

- Memory usage trends
- Cache hit/miss ratios
- Queue depths and processing latency
- WebSocket stability
- Composite health scoring for operational decisions
