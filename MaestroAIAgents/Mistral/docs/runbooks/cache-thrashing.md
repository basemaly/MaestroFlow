---
type: runbook
title: Cache Thrashing - Runbook
created: 2026-03-21
tags:
  - cache
  - performance
  - observability
---

# Alert: Cache Thrashing Detected

## Description

This alert fires when cache evictions exceed **100 per minute**, indicating the cache is too small for the working set or TTL values are too aggressive.

**Alert Level:** WARNING

---

## Likely Causes

1. **Cache Too Small**
   - Working set size > cache capacity
   - Sudden spike in distinct keys

2. **TTL Too Aggressive**
   - Expiration time too short
   - Items evicted before reuse

3. **LRU Policy Issues**
   - High cardinality queries creating many unique cache keys
   - Uneven access distribution

4. **Memory Pressure**
   - System running low on memory
   - Cache evicting to free space for other operations

---

## Troubleshooting

### 1. Verify Eviction Rate
```bash
# Check eviction metrics
curl http://localhost:8000/metrics | grep cache_evictions_total
```

### 2. Analyze Cache Hit Ratio
```bash
# In Grafana: "Cache Hit Ratio Trend" panel
# If hit ratio < 20%, cache is ineffective
```

### 3. Check Cache Capacity vs Working Set
```python
# Identify distinct keys being accessed
# Compare to cache max size

# For Redis:
redis-cli INFO memory
# Check used_memory vs maxmemory

# For in-memory cache:
# Check cache_size configuration
```

---

## Resolution

**If Cache Too Small:**
```python
# In backend/src/config/observability.py
CACHE_MAX_SIZE_MB = 512  # Increase from current value

# Or for Redis:
redis.config_set('maxmemory', '1gb')
```

**If TTL Too Short:**
```python
# Review TTL settings in cache operations
# Extend TTL if data is relatively static
cache.set(key, value, ttl_seconds=3600)  # Increase from shorter value
```

**Monitor Results:**
- Eviction rate should drop below 10/min within 5 minutes
- Hit ratio should improve within 15 minutes

---

## Prevention

- Set cache size based on actual working set + 20% headroom
- Use appropriate TTL for data type (frequent: 1h, infrequent: 4h+)
- Monitor cache metrics continuously
