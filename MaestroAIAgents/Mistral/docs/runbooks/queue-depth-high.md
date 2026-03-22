---
type: runbook
title: Queue Depth High - Runbook
created: 2026-03-21
tags:
  - queue
  - performance
  - observability
---

# Alert: Queue Depth Near Capacity

## Description

This alert fires when queue depth exceeds **80% of maximum capacity** for **2 minutes**. This indicates task processing is falling behind task submission.

**Alert Level:** WARNING

---

## Likely Causes

1. **Task Processing Slowdown**
   - External service timeout/slow response
   - Database contention
   - CPU/memory constraints

2. **Task Submission Spike**
   - Batch job creating many tasks simultaneously
   - Traffic surge
   - Scheduled job overlap

3. **Queue Worker Issues**
   - Worker crashed or unresponsive
   - Worker deadlocked
   - Insufficient worker instances

---

## Troubleshooting

### 1. Check Queue Depth and Capacity
```bash
# Via Prometheus/Grafana
# Dashboard: "Queue Depth" gauge panel
# Compare depth to max_depth

# Via API (if available)
curl http://localhost:8000/health | jq '.components.queue'
```

### 2. Analyze Processing Latency
```bash
# Check p95/p99 latency
# If latency spiked, processing became slow

# Possible causes:
# - Slow database query
# - External API timeout
# - CPU spike
```

### 3. Check Worker Status
```bash
# Verify workers are running
ps aux | grep worker

# Check worker logs
tail -100 logs/worker.log | grep ERROR

# Monitor CPU/memory
top -b -n 1 | head -20
```

### 4. Analyze Task Distribution
```python
# Check if certain task types are accumulating
# In backend/src/tasks/
# Look for patterns: are specific task_types backing up?

# Sample code to check:
from backend.src.observability.queue_tracking import get_queue_tracker
tracker = get_queue_tracker()
for queue_name, depth in tracker._queue_depths.items():
    print(f"{queue_name}: {depth} tasks pending")
```

---

## Resolution

### Immediate (Scale Out Workers)
```bash
# If using process-based workers
systemctl start maestroflow-worker-2  # Start additional worker
systemctl start maestroflow-worker-3

# If using container-based
docker-compose up -d --scale worker=4  # Scale to 4 replicas
```

### Short-term (Optimize Processing)
```python
# Check for slow tasks
# Profile task execution:
import time

@track_queue_operation('task_queue', 'slow_task')
def process_task(task):
    start = time.time()
    
    # Identify what's slow
    result1 = slow_operation()  # Check duration
    result2 = external_api_call()  # Check duration
    
    duration = time.time() - start
    if duration > 5:
        logger.warning(f"Task took {duration}s: {task.id}")
    
    return result1, result2
```

### Long-term (Capacity Planning)
- Increase worker count to handle peak load
- Batch similar tasks for efficiency
- Implement task prioritization (critical vs non-critical)
- Use async/non-blocking I/O for external calls

---

## Monitoring

After resolution:
- Queue depth should return to < 20% capacity within 10 minutes
- Processing latency should normalize
- All workers should show activity

```bash
# Verify recovery
while true; do
  curl -s http://localhost:8000/health | jq '.components.queue'
  sleep 10
done
```

---

## Prevention

- Monitor queue depth during load testing
- Set worker count = (peak_tasks_per_sec * avg_task_duration)
- Implement circuit breakers for external API calls
- Use exponential backoff for retries
