---
type: runbook
title: Queue Latency SLA Breach - Runbook
created: 2026-03-21
tags:
  - queue
  - performance
  - sla
  - observability
---

# Alert: Queue Processing Latency Exceeds SLA

## Description

This alert fires when queue processing latency (95th percentile) exceeds the defined SLA threshold, typically **10 seconds**. This indicates the queue processing rate is slower than demand.

**Alert Level:** WARNING (or CRITICAL if sustained)

---

## Likely Causes

1. **Worker Capacity Insufficient**
   - Fewer workers than required for traffic
   - Recent traffic surge not matched with worker scaling
   - Worker process stuck or hung

2. **Slow Task Processing**
   - Individual tasks taking longer than baseline
   - External service latency (API, database)
   - CPU or memory contention

3. **Queue Buildup**
   - Tasks accumulating faster than being processed
   - Cascading slowdown from earlier failures
   - Dead-letter queue items blocking processing

4. **Resource Exhaustion**
   - Memory pressure causing GC pauses
   - Disk I/O saturation
   - Network bandwidth exhaustion

5. **Task Characteristics Change**
   - Larger payloads than usual
   - More complex computations
   - Different task mix requiring different resources

---

## Troubleshooting

### 1. Check Current Queue Depth
```bash
# Query metrics
curl http://localhost:8000/metrics | grep queue_depth

# Expected: < 80% of max capacity
# If > 90%: Immediate worker scaling needed
```

### 2. Monitor Worker Status
```bash
# Check active workers
ps aux | grep worker

# Check CPU/memory per worker
top -p $(pgrep -d',' -f worker)

# Expected: CPUs at 70-85% utilization (not maxed out)
```

### 3. Analyze Latency Distribution
```bash
# In Grafana: "Queue Latency Percentiles" panel
# Check:
# - p50 (median): Should be well below SLA
# - p95: Close to SLA threshold when alert fires
# - p99: Significantly above SLA (acceptable for outliers)
```

### 4. Identify Slow Tasks
```bash
# Query logs for slow task processing
grep "task completed" /var/log/maestroflow.log | grep -E "duration>10s" | head -5

# Or query database if task completion is logged
SELECT task_type, COUNT(*), AVG(duration_seconds) 
FROM task_completions 
WHERE completed_at > NOW() - INTERVAL 5 MINUTE
GROUP BY task_type
ORDER BY AVG(duration_seconds) DESC;
```

### 5. Check External Dependencies
```bash
# Database query latency
curl http://localhost:8000/metrics | grep db_query_duration_seconds

# If p99 > 500ms: Database is slow
# Solution: Check query plans, add indexes, scale DB

# External API latency
grep "external_api" /var/log/maestroflow.log | grep -E "latency|duration" | head -10
```

### 6. Monitor Dead-Letter Queue
```bash
# Check DLQ depth
curl http://localhost:8000/metrics | grep queue_dlq_messages_total

# If DLQ has items: May be blocking main queue
# Solution: Process DLQ items, investigate root cause
```

---

## Resolution

**If Workers Insufficient:**
```bash
# Scale workers immediately
# For Docker Compose:
docker-compose up -d --scale worker=10

# For Kubernetes:
kubectl scale deployment maestroflow-worker --replicas=10

# Expected: Queue depth drops within 2-3 minutes
# Latency improves within 5-10 minutes
```

**If Worker Process Stuck:**
```bash
# Restart all workers
docker-compose restart worker

# Or kubectl delete all worker pods
kubectl delete pods -l app=maestroflow-worker
```

**If External Service Slow:**
- Check external service status page
- Review network latency (ping, traceroute)
- Implement timeout and retry logic if not present
- Consider circuit breaker pattern

**If Resource Exhaustion:**
```bash
# Check memory usage
free -h
docker stats

# If memory critical:
# 1. Increase container/pod memory limits
# 2. Profile for memory leaks
# 3. Reduce batch size if processing batches

# If disk I/O:
# 1. Check disk usage: df -h
# 2. Monitor I/O: iostat -x 1
# 3. Archive old data, increase disk capacity
```

---

## Monitoring Results

**After Scale-Out:**
- Queue depth should drop within 2-3 minutes
- Latency p95 should improve within 5 minutes
- SLA compliance should reach > 95% within 10 minutes

**After Restart:**
- Service should be up within 30 seconds
- Queue draining should resume immediately

**Success Criteria:**
- p95 latency < SLA threshold (default: 10s)
- Queue depth < 50% capacity
- No sustained alerts over 5-minute window

---

## Prevention

- Set worker count based on expected throughput + 30% headroom
- Use autoscaling: Scale up if queue depth > 60%, scale down if < 20%
- Monitor task latency distribution continuously
- Implement task timeouts to prevent hung tasks
- Regular load testing to validate capacity
- Set up alerts for queue depth trends (not just thresholds)
