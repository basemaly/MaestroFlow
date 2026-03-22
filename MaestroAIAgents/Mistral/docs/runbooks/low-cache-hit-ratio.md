---
type: runbook
title: Low Cache Hit Ratio - Runbook
created: 2026-03-21
tags:
  - cache
  - performance
  - observability
---

# Alert: Low Cache Hit Ratio

## Description

This alert fires when cache hit ratio drops below **20%** for 5 minutes, indicating the cache is not effectively serving requests or the working set is too large for the cache size.

**Alert Level:** WARNING

---

## Likely Causes

1. **Cache Too Small for Working Set**
   - Recent traffic spike with new access patterns
   - Increased distinct cache keys
   - Application scaling with larger working set

2. **Ineffective Cache Keys**
   - Cache keys too specific (per-user, per-request)
   - Insufficient key reuse
   - Key generation including timestamps or IDs

3. **TTL Expiration**
   - Items expiring before reuse
   - High ratio of misses are cache misses due to TTL

4. **Cache Invalidation Too Aggressive**
   - Manual cache clears on every deploy
   - Frequent cache invalidation logic
   - Mass invalidation of related keys

5. **Workload Characteristics**
   - One-off queries that don't benefit from caching
   - Highly variable query patterns
   - Batch processing with no repeated keys

---

## Troubleshooting

### 1. Verify Actual Hit Ratio
```bash
# Check cache metrics over last 5 minutes
curl http://localhost:8000/metrics | grep cache_hit_ratio
# Expected: > 0.20 (20%)
```

### 2. Analyze Cache Operations
```bash
# In Grafana: "Cache Hit Ratio Trend" panel
# Check for recent drops correlating with:
# - Deployment
# - Traffic spike
# - Configuration change
```

### 3. Review Cache Key Patterns
```python
# Check what keys are being cached
# Log cache operations to identify patterns

# In backend code, look for:
# cache.get(key)  # What is the key format?
# cache.set(key, value)  # How specific?

# High cardinality keys (bad):
cache_key = f"user:{user_id}:profile"  # One entry per user

# Low cardinality keys (good):
cache_key = "profiles_index"  # Reusable by many requests
```

### 4. Check TTL Configuration
```bash
# Query Redis if using Redis cache:
redis-cli TTL your_cache_key  # -1 = no expiry, -2 = expired

# Or check in-memory cache config
# Look for cache.set() calls with short TTLs
```

### 5. Analyze Request Patterns
```bash
# Check logs for repeated queries
grep "cache miss" /var/log/maestroflow.log | head -20

# Count unique cache keys being accessed
grep "cache key" /var/log/maestroflow.log | cut -d: -f2 | sort | uniq -c | sort -rn | head -10
```

---

## Resolution

**If Cache Too Small:**
- Increase cache capacity
- For Redis: `redis.config_set('maxmemory', '2gb')`
- For in-memory: Adjust `CACHE_MAX_SIZE` in config
- Monitor hit ratio over next 15 minutes

**If Keys Too Specific:**
- Refactor cache key design to be less cardinality-heavy
- Use hierarchical keys (e.g., "category:items" instead of "category:item:123")
- Batch similar items under shared cache keys where possible

**If TTL Too Short:**
```python
# Review and extend TTL for data that is relatively static
cache.set(key, value, ttl_seconds=3600)  # Increase from current value
```

**If Invalidation Too Aggressive:**
- Review cache invalidation logic
- Avoid mass invalidations; invalidate only affected keys
- Use cache versioning instead of clearing (add version suffix to keys)

**Monitor Results:**
- Hit ratio should improve within 5-10 minutes after changes
- Target: Hit ratio ≥ 60% for well-designed caches
- For real-time data: Acceptable range 30-50%

---

## Prevention

- Design cache keys for maximum reuse (low cardinality)
- Use appropriate TTL based on data freshness requirements
- Monitor hit ratio continuously; alert when < 20%
- Conduct quarterly cache key design reviews
- Test cache effectiveness under production-like load
