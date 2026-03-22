---
type: runbook
title: High Memory Growth Rate - Runbook
created: 2026-03-21
tags:
  - memory
  - leak-detection
  - observability
related:
  - Memory Thresholds
---

# Alert: High Memory Growth Rate

## Description

This alert fires when process memory is growing at more than **5 MB/minute** for a sustained period of **10 minutes**. This pattern typically indicates a potential memory leak.

**Alert Level:** WARNING  
**Duration:** 10 minutes

---

## Likely Causes

1. **Object Accumulation Without Release**
   - Cached objects not being evicted
   - Event listeners not being unregistered
   - Database connections held in pool without cleanup

2. **Unbounded Collections**
   - Lists/dictionaries growing without bounds
   - Thread-local storage not being cleaned
   - Request context data accumulating across requests

3. **Third-Party Library Leaks**
   - Dependencies with memory issues
   - Improper initialization of external libraries

4. **Legitimate Workload Increase**
   - Concurrent users growing
   - Cache being populated for new data

---

## Troubleshooting Steps

### 1. Verify Memory Usage Against Threshold
```bash
# Check current memory consumption
curl http://localhost:8000/metrics | grep process_memory_rss_bytes

# Compare to threshold (default 1024 MB)
# If < 80% of threshold: system is healthy
# If 80-100% of threshold: degraded
# If > 100% of threshold: critical
```

### 2. Check Memory Growth Over Time
```bash
# Query Prometheus for 1-hour memory trend
# In Grafana: use "Memory Usage Over Time" dashboard
# Look for slope: if consistently increasing > 1 MB/min, leak likely exists
```

### 3. Identify Consuming Processes
```bash
# Get heap dump (Python only, requires tracemalloc)
# Enable in app startup:
import tracemalloc
tracemalloc.start()

# Capture snapshot after 15 minutes
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
```

### 4. Check Recent Deployments
- Was there a code change in the last few hours?
- Did dependency versions update?
- Is this happening across all instances or just one?

---

## Mitigation Actions

### Immediate (0-5 minutes)

**Option A: Restart Service**
```bash
# Kill and restart the app (if stateless)
systemctl restart maestroflow-api
# Or if using container
docker-compose restart maestroflow-api
```

**Option B: Scale Out**
```bash
# If using load balancer, temporarily route traffic away from affected instance
# while you investigate
```

### Short-term (5-30 minutes)

**Enable Debug Logging**
```python
# In backend/src/config/observability.py
MEMORY_DEBUG_LOGGING = True

# Restart app
# Check logs for "Memory warning" messages indicating which component is leaking
```

**Analyze Recent Changes**
```bash
# Compare current code to previous version
git log --oneline -10

# Review changes to:
# - backend/src/observability/cache_tracking.py
# - backend/src/routers/*.py (new endpoints)
# - Any async task handlers
```

### Long-term (> 30 minutes)

**Run Profiler**
```bash
# Install memory_profiler
pip install memory-profiler

# Profile top functions
python -m memory_profiler backend/src/main.py

# Compare results to baseline
```

**Review Common Leak Patterns**
- [ ] Event listeners registered but never unregistered
- [ ] Database connections pooled indefinitely
- [ ] Cache TTL values set too high (or infinite)
- [ ] Circular references between objects
- [ ] Global state accumulating without bounds

---

## Resolution

Once cause is identified:

1. **If Code Bug:** Deploy hotfix, redeploy to production
2. **If Dependency Issue:** Upgrade/downgrade package version
3. **If Workload:** Increase memory threshold or scale horizontally

### Verify Fix
```bash
# After fix deployment, monitor memory growth rate
# Should drop back below 1 MB/min within 10 minutes

# Use dashboard: "Memory Growth Rate" panel
# Confirm growth_rate < threshold for 30+ minutes
```

---

## Prevention

- **Enable memory limits:** Set container memory limit 80% of threshold
- **Unit tests:** Add tests for resource cleanup
- **Integration tests:** Run for 30+ minutes with load testing
- **Code review:** Check all async code for proper cleanup

---

## Escalation

If memory continues growing after mitigation:
1. Engage backend team lead
2. Request detailed profiling/heap dump analysis
3. Consider running database cleanup jobs if applicable
4. Check if upstream service is sending malformed data causing parsing errors
