---
type: guide
title: Alert Runbooks
created: 2026-03-21
tags:
  - alerts
  - runbooks
  - incident-response
  - operations
---

# MaestroFlow Alert Runbooks

Incident response guides for alerts fired by the MaestroFlow monitoring system. Each runbook includes likely causes, debugging steps, and mitigation actions.

---

## Memory Alerts

### Alert: HighMemoryGrowthRate

**Severity:** ⚠️ WARNING  
**Duration:** Fires if condition persists for 10 minutes  
**Description:** Process memory growing faster than normal (> 5 MB/min)

#### Likely Causes

1. **Memory leak in application code**
   - Unbounded collection accumulating data
   - Circular references preventing garbage collection
   - Connection/resource not being released

2. **Metric label cardinality explosion**
   - Too many unique metric label combinations
   - Creates new time-series for each combination
   - Example: endpoint label with many unique paths

3. **Langfuse trace buffering**
   - Traces waiting to be sent to Langfuse
   - Network issues preventing send
   - Buffer size limit exceeded

4. **Cache memory leak**
   - Cache entries never evicted
   - TTL not implemented
   - Memory limit not enforced

#### Debugging Steps

**Step 1: Check current memory usage**
```bash
curl http://localhost:8000/health?verbose=true | jq .checks.memory
```

Expected output:
```json
{
  "status": "warning",
  "memory_mb": 512,
  "threshold_mb": 1024,
  "growth_rate_mb_per_minute": 6.5
}
```

**Step 2: Check memory growth trend (last 1 hour)**
```
# In Prometheus, query:
rate(process_memory_usage_bytes[5m]) / 1024 / 1024
```

If consistently > 5 MB/min, memory leak confirmed.

**Step 3: Check metric cardinality**
```bash
# In Prometheus UI, query for cardinality:
topk(10, count by (__name__) ({{__name__=~".+"}}) > 100)
```

Look for metrics with thousands of time-series.

**Step 4: Check for unbounded collections**
```python
# Review application code for:
# - Lists that grow without limit
# - Dictionaries never cleared
# - Class attributes accumulating data

# Example bad pattern:
self.user_history = []  # Global, never cleared

# Example good pattern:
from collections import deque
self.user_history = deque(maxlen=1000)  # Auto-evict oldest
```

**Step 5: Check Langfuse integration**
```bash
# In application logs, search for:
# "Langfuse: failed to send", "network error"

# View Langfuse buffer size
curl http://localhost:8000/metrics | grep langfuse_buffer
```

#### Mitigation Actions

**Immediate (Stop the leak):**

1. **Restart the application**
   ```bash
   pkill -f "python3 backend/main.py"
   sleep 2
   python3 backend/main.py &
   ```
   
   Memory should return to baseline. If not, continue to next steps.

2. **Reduce metric cardinality**
   ```python
   # In middleware or before recording metric:
   # Normalize high-cardinality labels
   
   endpoint = request.url.path
   if endpoint not in KNOWN_ENDPOINTS:
       endpoint = "OTHER"  # Group unknown endpoints
   
   metrics.record_request(endpoint, status)
   ```

3. **Check and fix Langfuse configuration**
   ```bash
   # In .env
   LANGFUSE_ENABLED=false  # Temporarily disable
   # or
   LANGFUSE_SAMPLE_RATE=0.1  # Sample 10% of traces
   
   # Restart app
   pkill -f "python3 backend/main.py"
   python3 backend/main.py &
   ```

4. **Review and fix cache implementations**
   ```python
   # Bad: unbounded cache
   cache = {}
   
   # Good: bounded cache with TTL
   from cachetools import TTLCache
   cache = TTLCache(maxsize=1000, ttl=3600)  # 1000 items, 1 hour TTL
   ```

**Long-term (Fix the root cause):**

1. Use Python profiler to identify leak:
   ```bash
   python3 -m memory_profiler backend/main.py
   ```

2. Add metrics for collection sizes:
   ```python
   metrics.gauge('collection_size', len(my_dict), labels={'collection': 'user_cache'})
   ```

3. Implement automated tests for memory:
   ```python
   def test_no_memory_leak():
       """Verify memory doesn't grow under load."""
       initial_memory = psutil.Process().memory_info().rss
       
       for _ in range(10000):
           make_request()
       
       final_memory = psutil.Process().memory_info().rss
       growth_mb = (final_memory - initial_memory) / 1024 / 1024
       
       assert growth_mb < 50, f"Memory grew by {growth_mb} MB"
   ```

---

### Alert: MemoryThresholdExceeded

**Severity:** 🚨 CRITICAL  
**Duration:** Fires if memory > 1GB for 2 minutes  
**Description:** Process memory exceeds configured threshold

#### Likely Causes

Same as HighMemoryGrowthRate, but more severe.

#### Mitigation Actions

1. **Emergency restart**
   ```bash
   # Kill existing process
   pkill -9 -f "python3 backend/main.py"
   sleep 5
   
   # Restart
   python3 backend/main.py &
   ```

2. **Increase threshold if needed**
   ```bash
   # In .env
   MEMORY_THRESHOLD_MB=2048  # Increase to 2GB
   
   # Restart app
   ```

3. **Check for upstream issues**
   - Is a data migration running?
   - Is a large batch job processing?
   - Is there a sudden traffic spike?

4. **If memory stays high after restart**
   - Roll back recent code changes
   - Reduce request load (throttle traffic)
   - Scale horizontally (add more replicas)

---

## Database Alerts

### Alert: SlowDatabaseQueries

**Severity:** ⚠️ WARNING  
**Duration:** Fires if p99 latency > 1s for 5 minutes  
**Description:** Database queries are slower than expected

#### Likely Causes

1. **Missing database index**
   - Query performing full table scan
   - JOIN on unindexed column
   - WHERE clause on unindexed column

2. **Database connection pool exhaustion**
   - All connections in use
   - Queries waiting for available connection
   - Connection pool size too small

3. **High table contention**
   - Many concurrent writes to same table
   - Locks held by other queries
   - Lock timeout or deadlock

4. **Insufficient database resources**
   - CPU at 100%
   - Disk I/O bottleneck
   - Memory pressure (swapping to disk)

#### Debugging Steps

**Step 1: Identify slow queries**
```sql
-- In PostgreSQL
SELECT query, mean_exec_time, max_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 1000  -- > 1 second
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Step 2: Check query plan**
```sql
-- Analyze slow query
EXPLAIN ANALYZE
SELECT * FROM users WHERE email = 'test@example.com';

-- Look for:
-- - Seq Scan (full table scan) → needs index
-- - Sort (expensive) → use index on sort column
-- - Nested Loop (expensive) → optimize JOIN
```

**Step 3: Check connection pool status**
```bash
# Query Prometheus
histogram_quantile(0.95, db_connection_wait_seconds)

# If > 0.5s, pool is congested
```

**Step 4: Check database resource usage**
```bash
# CPU usage
top -p $(pidof postgres)

# Disk I/O
iostat -x 1 10

# Memory
free -h
```

#### Mitigation Actions

**Immediate:**

1. **Add missing index**
   ```sql
   -- For slow WHERE clause
   CREATE INDEX idx_users_email ON users(email);
   
   -- For slow JOIN
   CREATE INDEX idx_orders_user_id ON orders(user_id);
   ```

2. **Increase connection pool size**
   ```bash
   # In .env
   DB_POOL_MAX_SIZE=20  # Increase from 10
   
   # Restart app
   ```

3. **Kill long-running queries**
   ```sql
   -- Find long-running queries
   SELECT pid, query, query_start
   FROM pg_stat_activity
   WHERE query_start < NOW() - INTERVAL '5 minutes';
   
   -- Kill if safe
   SELECT pg_terminate_backend(pid);
   ```

**Long-term:**

1. **Regular index maintenance**
   ```sql
   -- Identify unused indexes
   SELECT schemaname, tablename, indexname, idx_scan
   FROM pg_stat_user_indexes
   WHERE idx_scan = 0
   ORDER BY pg_relation_size(indexrelid) DESC;
   
   -- Drop unused
   DROP INDEX idx_name;
   ```

2. **Query optimization**
   ```sql
   -- Break large query into smaller ones
   -- Use EXPLAIN to find bad plans
   -- Consider materialized views for complex aggregations
   ```

3. **Database tuning**
   - Increase PostgreSQL `shared_buffers` (25% of RAM)
   - Tune `work_mem` for sort operations
   - Enable `log_min_duration_statement` to capture slow queries

---

### Alert: HighDBConnectionWaitTime

**Severity:** ⚠️ WARNING  
**Duration:** Fires if p95 wait time > 0.5s for 5 minutes  
**Description:** Requests waiting long for database connections

#### Mitigation Actions

1. **Increase connection pool size**
   ```bash
   # In .env
   DB_POOL_MAX_SIZE=30
   
   # Restart app
   ```

2. **Reduce query duration** (see SlowDatabaseQueries runbook above)

3. **Optimize connection reuse**
   ```python
   # Ensure connections are returned promptly
   async with pool.acquire() as conn:
       result = await conn.fetch(query)
   # Connection automatically returned here
   ```

4. **Add connection pool metrics**
   ```python
   metrics.gauge('db_connections_idle', pool.get_idle_size())
   ```

---

## Queue Alerts

### Alert: QueueDepthHigh

**Severity:** ⚠️ WARNING  
**Duration:** Fires if depth > 800 for 2 minutes  
**Description:** Queue has too many items waiting (running out of capacity)

#### Likely Causes

1. **Queue consumer is slow**
   - Processing taking longer than expected
   - Consumer crashed or hung
   - Consumer not running at all

2. **Increased traffic**
   - Sudden spike in requests
   - New feature driving more queue items
   - Batch job adding bulk items

3. **Resource constraints on consumer**
   - CPU maxed out
   - Memory constrained
   - Disk I/O bottleneck

#### Debugging Steps

**Step 1: Check queue processor status**
```bash
# Is the consumer running?
ps aux | grep queue_processor

# Is it responsive?
curl http://localhost:8000/health?verbose=true | jq '.checks.queue'
```

**Step 2: Check processing latency**
```
# In Prometheus:
histogram_quantile(0.95, queue_processing_latency_seconds)
```

If p95 > 10 seconds, consumer is slow.

**Step 3: Check recent traffic**
```
# In Prometheus:
rate(queue_depth_increases_total[5m])

# If high rate, traffic spike confirmed
```

#### Mitigation Actions

**Immediate:**

1. **Scale consumer horizontally**
   ```bash
   # Start additional consumer processes
   python3 -m queue_processor &
   python3 -m queue_processor &  # 2nd instance
   ```

2. **Restart slow consumer**
   ```bash
   pkill -f queue_processor
   sleep 2
   python3 -m queue_processor &
   ```

3. **Reduce queue item throughput temporarily**
   - Rate limit incoming requests
   - Reject new items with 503 Service Unavailable
   - Send 202 Accepted and queue asynchronously

**Long-term:**

1. **Optimize consumer performance**
   - Profile slow operations
   - Add batch processing (process 10 items at once)
   - Cache frequently accessed data

2. **Increase queue capacity**
   ```bash
   # In .env
   QUEUE_MAX_DEPTH=2000  # Increase from 1000
   ```

3. **Monitor and alert on consumer health**
   ```python
   metrics.gauge('queue_consumer_health', health_score)
   ```

---

### Alert: QueueErrorRateHigh

**Severity:** 🚨 CRITICAL  
**Duration:** Fires if error rate > 5% for 5 minutes  
**Description:** Too many items failing to process

#### Likely Causes

1. **Bug in queue item processing code**
2. **Invalid item data in queue**
3. **External service dependency unavailable** (API, database, etc.)
4. **Insufficient permissions or credentials**

#### Debugging Steps

**Step 1: Check error logs**
```bash
# View logs for queue processor
tail -f /var/log/maestroflow/queue.log | grep ERROR

# Look for stack traces and error messages
```

**Step 2: Check dead letter queue (DLQ)**
```sql
-- Items that failed too many times
SELECT item_id, error_message, fail_count
FROM queue_dlq
ORDER BY fail_count DESC
LIMIT 10;
```

**Step 3: Check dependency status**
```bash
# Is external API responding?
curl https://api.example.com/health

# Can we reach database?
psql -U maestroflow -d maestroflow -c "SELECT 1"
```

#### Mitigation Actions

1. **Review recent code changes**
   - Revert if bug introduced
   - Deploy hotfix
   - Test in staging first

2. **Restore external dependencies**
   - Restart external service
   - Check API keys and credentials
   - Verify network connectivity

3. **Clear invalid items from queue**
   ```sql
   -- Review failed items
   SELECT * FROM queue_dlq WHERE error LIKE '%invalid%' LIMIT 5;
   
   -- If safe to discard, remove
   DELETE FROM queue_dlq WHERE error LIKE '%invalid%';
   ```

4. **Implement circuit breaker**
   ```python
   # Stop calling failing external service
   from circuitbreaker import circuit
   
   @circuit(failure_threshold=5, recovery_timeout=60)
   async def call_external_api():
       return await api.request()
   ```

---

## Cache Alerts

### Alert: LowCacheHitRatio

**Severity:** ⚠️ WARNING  
**Duration:** Fires if hit ratio < 20% for 5 minutes  
**Description:** Cache is not effective (many misses)

#### Likely Causes

1. **Cache too small**
   - Items evicted before reuse
   - High diversity of requested items

2. **Bad cache key design**
   - Keys too specific (don't match future requests)
   - Missing cache for frequently accessed data

3. **No cache for expensive operations**
   - Database queries not cached
   - API calls not cached
   - Computations not cached

4. **Cache not warmed on startup**
   - High misses until cache fills

#### Debugging Steps

**Step 1: Check cache effectiveness metrics**
```
# In Prometheus
cache_hits_total vs cache_misses_total

# Calculate ratio
cache_hits_total / (cache_hits_total + cache_misses_total)
```

**Step 2: Check cache implementation**
```python
# Review cache usage patterns
# Look for:
# - Appropriate cache keys
# - Adequate cache size
# - TTL appropriate for data freshness

# Example good pattern:
cache_key = f"user:{user_id}:profile"  # Specific but reusable
cache_ttl = 3600  # 1 hour for profile data
```

**Step 3: Check what's being cached**
```sql
-- What are top missing keys?
SELECT key, miss_count
FROM cache_miss_log
GROUP BY key
ORDER BY miss_count DESC
LIMIT 10;
```

#### Mitigation Actions

1. **Increase cache size**
   ```python
   # In config
   CACHE_MAX_SIZE = 10000  # Increase from 1000
   ```

2. **Optimize cache keys**
   ```python
   # Bad: Too specific
   cache_key = f"user:{user_id}:post:{post_id}:version:{version}"
   
   # Good: Reusable
   cache_key = f"user:{user_id}:posts"
   ```

3. **Add caching for expensive operations**
   ```python
   # Cache database queries
   @cache(ttl=300)
   async def get_user_approvals(user_id):
       return await db.fetch(query)
   
   # Cache API calls
   @cache(ttl=3600)
   async def get_exchange_rate(from_currency, to_currency):
       return await external_api.get_rate(...)
   ```

4. **Warm cache on startup**
   ```python
   async def startup_event():
       # Preload frequently accessed data
       await cache.set('config:global', load_global_config())
       await cache.set('rates:USD', load_usd_rates())
   ```

---

## WebSocket Alerts

### Alert: WebSocketErrorRateHigh

**Severity:** ⚠️ WARNING  
**Duration:** Fires if error rate > 5% for 5 minutes  
**Description:** High error rate on WebSocket connections

#### Likely Causes

1. **Network instability**
   - Packet loss
   - Connection timeouts

2. **Message handling bugs**
   - Exception in message handler
   - Invalid message format

3. **Resource exhaustion**
   - Out of memory
   - File descriptor limit

#### Debugging Steps

**Step 1: Check WebSocket error logs**
```bash
tail -f /var/log/maestroflow/websocket.log | grep ERROR
```

**Step 2: Check active connections**
```
# In Prometheus
websocket_connections_active
```

**Step 3: Check message handling code**
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        await websocket.accept()
        while True:
            data = await websocket.receive_text()
            # Errors here trigger alert
            result = process_message(data)
            await websocket.send_json(result)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        # Record error metric
        metrics.websocket_errors.inc()
```

#### Mitigation Actions

1. **Add error handling**
   ```python
   try:
       result = process_message(data)
   except ValueError as e:
       logger.warning(f"Invalid message: {e}")
       await websocket.send_json({"error": "invalid_message"})
   except Exception as e:
       logger.error(f"Unexpected error: {e}")
       await websocket.close(code=1011)  # Server error
   ```

2. **Add message validation**
   ```python
   from pydantic import BaseModel, ValidationError
   
   class Message(BaseModel):
       action: str
       data: dict
   
   try:
       msg = Message(**data)
   except ValidationError as e:
       await websocket.send_json({"error": "invalid_schema"})
   ```

3. **Monitor resource usage**
   ```python
   @app.on_event("startup")
   async def monitor_resources():
       while True:
           mem = psutil.Process().memory_info().rss / 1024 / 1024
           if mem > 500:  # 500 MB
               logger.warning(f"High memory: {mem} MB")
           await asyncio.sleep(30)
   ```

---

## HTTP Request Alerts

### Alert: HighHTTPErrorRate

**Severity:** ⚠️ WARNING  
**Duration:** Fires if 5xx error rate > 5% for 5 minutes  
**Description:** High proportion of requests returning 5xx errors

#### Likely Causes

1. **Exception in request handler**
2. **External dependency failure** (database, API, cache)
3. **Invalid request data**
4. **Resource constraints**

#### Debugging Steps

**Step 1: Check error logs**
```bash
# View recent error logs
grep -i "exception\|error\|traceback" /var/log/maestroflow/app.log | tail -20
```

**Step 2: Identify which endpoints are failing**
```
# In Prometheus
rate(http_requests_total{status=~"5.."}[5m]) by (endpoint)
```

**Step 3: Check dependency status**
- Database: `curl http://localhost:8000/health?verbose=true | jq '.checks.database'`
- Cache: `curl http://localhost:8000/health?verbose=true | jq '.checks.cache'`
- External APIs: Check status pages

#### Mitigation Actions

1. **Restart application**
   ```bash
   pkill -f "python3 backend/main.py"
   sleep 2
   python3 backend/main.py &
   ```

2. **Restore failing dependencies**
   - Restart database
   - Restart cache
   - Check external API status

3. **Inspect and fix error-causing code**
   - Review recent changes
   - Add error handling
   - Add validation

4. **Enable graceful degradation**
   ```python
   try:
       data = await get_from_cache(key)
   except CacheError:
       logger.warning("Cache unavailable, falling back to database")
       data = await get_from_database(key)
   ```

---

## LLM Alerts

### Alert: HighLLMCosts

**Severity:** ℹ️ INFO  
**Duration:** Fires if cost/hour > $100 for 10 minutes  
**Description:** LLM API spending is high

#### Likely Causes

1. **Increased traffic**
   - More users making requests
   - Batch job processing

2. **Expensive model usage**
   - Using gpt-4 instead of gpt-3.5
   - Long prompts with many tokens

3. **Token waste**
   - Retrying failed requests
   - Not caching responses
   - Inefficient prompt design

#### Debugging Steps

**Step 1: Check cost by model**
```
# In Prometheus
llm_cost_usd_total by (model)
```

**Step 2: Check token usage**
```
# In Prometheus
llm_tokens_used_total by (model, token_type)
```

**Step 3: Check request rate**
```
# In Prometheus
rate(llm_calls_total[5m])
```

#### Mitigation Actions

1. **Optimize prompt design**
   ```python
   # Shorter prompts = fewer tokens = less cost
   # Bad: Include full conversation history
   prompt = f"{full_history}\nQuestion: {question}"
   
   # Good: Summarize context
   summary = await summarize_history(history)
   prompt = f"Context: {summary}\nQuestion: {question}"
   ```

2. **Implement response caching**
   ```python
   cache_key = hash_prompt(prompt)
   cached_response = await cache.get(cache_key)
   
   if cached_response:
       return cached_response
   
   response = await llm.complete(prompt)
   await cache.set(cache_key, response, ttl=3600)
   return response
   ```

3. **Switch to cheaper models**
   ```python
   # If accuracy permits, use gpt-3.5-turbo instead of gpt-4
   model = "gpt-3.5-turbo"  # ~1/10 cost of gpt-4
   ```

4. **Implement rate limiting**
   ```python
   from slowapi import Limiter
   
   limiter = Limiter(key_func=get_user_id)
   
   @app.post("/api/complete")
   @limiter.limit("10/minute")
   async def complete(request):
       pass
   ```

---

## Runbook Format Template

For creating additional runbooks:

```markdown
### Alert: AlertName

**Severity:** LEVEL (Critical/Warning/Info)
**Duration:** Fires if condition persists for X minutes
**Description:** What the alert means

#### Likely Causes

1. Cause 1
2. Cause 2
3. Cause 3

#### Debugging Steps

**Step 1: Description**
```bash
# Commands to run
```

**Step 2: Description**
```bash
# Commands to run
```

#### Mitigation Actions

**Immediate:**
1. Action 1
2. Action 2

**Long-term:**
1. Action 1
2. Action 2
```

---

## Further Resources

- [Prometheus Alerting](https://prometheus.io/docs/alerting/overview/)
- [Alert Best Practices](https://prometheus.io/docs/practices/alerting/)
- [Runbook Template](https://docs.google.com/document/d/199PqyG3UsyXlwieHaqbGiWVa8eMXqS35_9_Or-I5Or0/)
