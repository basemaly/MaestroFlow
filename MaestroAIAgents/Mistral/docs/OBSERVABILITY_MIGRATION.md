---
type: reference
title: Observability Migration & Rollout Plan
created: 2026-03-22
tags:
  - deployment
  - migration
  - rollout
  - observability
related:
  - "[[OBSERVABILITY]]"
  - "[[OBSERVABILITY_TROUBLESHOOTING]]"
---

# Observability Migration & Rollout Plan

## Overview

This document outlines a phased rollout strategy for deploying the observability system to production. The phased approach minimizes risk by validating each component before deploying the next layer, with clear rollback procedures at each stage.

**Timeline:** 4 weeks, starting with Phase 1

---

## Phase 1: Metrics Infrastructure & Health Endpoints (Week 1)

### Objective
Deploy Prometheus metrics collection and health check endpoints. This foundation layer has minimal risk because:
- Metrics are read-only (no side effects)
- Health checks don't modify state
- Can disable at runtime with `METRICS_ENABLED=false`

### Deployment

#### Pre-Deployment Validation
```bash
# 1. Code review
# - backend/src/observability/metrics.py
# - backend/src/routers/health.py
# - backend/main.py (middleware addition)

# 2. Unit tests pass
python -m pytest backend/tests/test_metrics.py -v
python -m pytest backend/tests/test_health_endpoints.py -v

# 3. Docker image builds
docker build -t maestroflow:phase1 .

# 4. docker-compose starts without errors
docker-compose -f docker-compose.yml up -d
docker-compose ps

# 5. Health checks respond
curl -f http://localhost:8000/health
curl -f http://localhost:8000/health/ready
curl -f http://localhost:8000/health/live
curl -f http://localhost:8000/metrics
```

#### Staging Deployment
```bash
# Deploy to staging environment
# 1. Set environment variables
export METRICS_ENABLED=true
export LANGFUSE_ENABLED=false  # Disabled for Phase 1
export PROMETHEUS_PORT=9090

# 2. Deploy with docker-compose
docker-compose up -d

# 3. Verify endpoints
for endpoint in "/" "/health" "/health/ready" "/health/live" "/metrics"; do
    curl -v http://localhost:8000$endpoint
done

# 4. Wait for Prometheus to scrape
sleep 30
curl http://localhost:9090/api/v1/targets

# 5. Verify metrics are being collected
curl http://localhost:9090/api/v1/query?query=up
curl http://localhost:9090/api/v1/query?query=http_requests_total
```

#### Monitoring During Phase 1
```promql
# Watch these metrics for 24 hours
- up{job="maestroflow"}          # Should be 1 (active)
- rate(http_requests_total[1m])  # Should match actual request rate
- http_request_duration_seconds   # Should show reasonable latencies
- process_resident_memory_bytes   # Baseline for comparison
```

### Success Criteria for Phase 1
- ✅ `/health` endpoint responds consistently (99.9% uptime)
- ✅ `/metrics` endpoint returns valid Prometheus format
- ✅ Prometheus scrapes metrics successfully
- ✅ No errors in application logs
- ✅ Metrics volume reasonable (< 100 metrics per endpoint)
- ✅ No memory leaks detected (stable growth)
- ✅ Health check latency < 50ms (P95)

### Rollback Plan for Phase 1
```bash
# If critical issues found during Phase 1:

# 1. Disable metrics collection immediately
export METRICS_ENABLED=false
docker-compose restart fastapi

# 2. Verify application is functional
curl http://localhost:8000/health

# 3. Investigate issues
docker logs maestroflow-fastapi-1 | tail -100

# 4. Fix and re-deploy to staging first
git revert <problematic-commit>
docker-compose up -d

# 5. Re-test before proceeding to Phase 2
```

---

## Phase 2: Langfuse Distributed Tracing (Week 2)

### Objective
Deploy distributed tracing with Langfuse. This layer adds:
- Request tracing across services
- LLM call tracking
- Error correlation
- User journey insights

### Deployment

#### Pre-Phase 2 Validation
```bash
# 1. Phase 1 metrics must be stable for 24+ hours
# Check metrics:
# - Uptime: 99.9%+
# - No memory growth > 1 MB/hour
# - P95 latency stable

# 2. Code review for Phase 2 changes
# - backend/src/observability/langfuse_client.py
# - backend/src/observability/request_context.py
# - backend/src/observability/middleware.py (context addition)

# 3. Integration tests pass
python -m pytest backend/tests/test_langfuse_integration.py -v
python -m pytest backend/tests/test_request_context.py -v

# 4. Langfuse configuration is correct
export LANGFUSE_PUBLIC_KEY="pk_xxx"
export LANGFUSE_SECRET_KEY="sk_xxx"
export LANGFUSE_HOST="https://cloud.langfuse.com"
export LANGFUSE_ENABLED=true
export LANGFUSE_SAMPLE_RATE=0.1  # Start with 10% sampling
```

#### Staging Deployment
```bash
# Deploy with Langfuse enabled (10% sampling)
docker-compose down
export LANGFUSE_ENABLED=true
export LANGFUSE_SAMPLE_RATE=0.1  # Only sample 10% of requests
docker-compose up -d

# Verify Langfuse connectivity
curl http://localhost:8000/health | jq '.observability.langfuse_enabled'

# Make test requests
for i in {1..100}; do
    curl http://localhost:8000/
done

# Wait 30 seconds for batched traces to send
sleep 30

# Check Langfuse dashboard for traces
# https://cloud.langfuse.com → Recent Traces
# Should see ~10 traces (10% of 100 requests)
```

#### Monitoring During Phase 2
```promql
- rate(http_requests_total[1m])        # Request volume baseline
- langfuse_traces_sent_total           # Should increment
- rate(langfuse_errors_total[1m])      # Should be near 0
- langfuse_api_duration_seconds        # P95 should be < 100ms
- process_resident_memory_bytes        # Watch for growth
- http_request_duration_seconds        # Should not increase
```

#### Gradual Sample Rate Increase
```
Day 1 (Phase 2): 10% sampling (LANGFUSE_SAMPLE_RATE=0.1)
Day 2-3: 25% sampling (LANGFUSE_SAMPLE_RATE=0.25)
Day 4-5: 50% sampling (LANGFUSE_SAMPLE_RATE=0.5)
Day 6-7: 100% sampling (LANGFUSE_SAMPLE_RATE=1.0)

Monitor at each step:
- Langfuse API latency (should stay < 100ms)
- HTTP request latency (should not increase > 5%)
- Memory growth (should stay < 1 MB/hour)
- Trace delivery success rate (should be > 99%)
```

### Success Criteria for Phase 2
- ✅ Traces appear in Langfuse dashboard (with 10s latency)
- ✅ Trace correlation with Prometheus metrics (matching request IDs)
- ✅ Request context (trace_id, user_id) properly propagated
- ✅ LLM calls traced with model, tokens, cost
- ✅ No increase in HTTP latency (< 5% increase at 100% sampling)
- ✅ Memory growth from Langfuse < 50 MB (from 62 MB to 112 MB max)
- ✅ No Langfuse connection errors in logs

### Rollback Plan for Phase 2
```bash
# If Langfuse causes issues:

# 1. Disable Langfuse immediately
export LANGFUSE_ENABLED=false
export LANGFUSE_SAMPLE_RATE=0

# 2. Restart app
docker-compose restart fastapi

# 3. Verify metrics still working
curl http://localhost:8000/metrics

# 4. Investigate Langfuse issues
# - Check network connectivity: curl https://cloud.langfuse.com
# - Check credentials: verify API keys
# - Check API rate limits: too many requests?

# 5. Reduce sample rate and retry
# Instead of disabling completely:
export LANGFUSE_ENABLED=true
export LANGFUSE_SAMPLE_RATE=0.01  # 1% sampling instead
docker-compose restart fastapi
```

---

## Phase 3: Advanced Monitoring (Week 3)

### Objective
Deploy advanced monitoring components:
- Memory tracking and alerts
- Queue depth monitoring
- Cache hit ratio tracking
- WebSocket connection monitoring

### Deployment

#### Pre-Phase 3 Validation
```bash
# 1. Phase 1 + Phase 2 must be stable for 7+ days
# - Zero unplanned restarts
# - < 5% error rate
# - Memory stable (no unbounded growth)

# 2. Code review for Phase 3
# - backend/src/observability/memory_tracking.py
# - backend/src/observability/queue_tracking.py
# - backend/src/observability/cache_tracking.py

# 3. Configuration flags set
export MEMORY_TRACKING_ENABLED=true
export QUEUE_TRACKING_ENABLED=true
export CACHE_TRACKING_ENABLED=true
export ADVANCED_MONITORING_ENABLED=true

# 4. Stress tests pass
python -m pytest backend/tests/test_memory_tracking.py -v
python -m pytest backend/tests/test_queue_tracking.py -v
python -m pytest backend/tests/test_cache_tracking.py -v
```

#### Staging Deployment
```bash
# Deploy with advanced monitoring
docker-compose down
export MEMORY_TRACKING_ENABLED=true
export QUEUE_TRACKING_ENABLED=true
export CACHE_TRACKING_ENABLED=true
docker-compose up -d

# Run load test to verify stability
# Using script from PERFORMANCE_BASELINE.md
python benchmark.py --duration=300

# Monitor for:
# - Memory growth (should be < 1 MB/min)
# - Metric cardinality (should stay < 5000)
# - Error rate (should be 0)
```

### Success Criteria for Phase 3
- ✅ Memory tracking shows accurate baseline
- ✅ Queue depth monitored and alerts trigger
- ✅ Cache hit ratio calculated correctly
- ✅ WebSocket connections tracked
- ✅ Advanced metrics don't impact latency
- ✅ No cardinality explosion (< 5000 unique metric series)

### Rollback Plan for Phase 3
```bash
# If advanced monitoring causes issues:

# Disable the problematic module
export MEMORY_TRACKING_ENABLED=false
export QUEUE_TRACKING_ENABLED=false
export CACHE_TRACKING_ENABLED=false

# Restart
docker-compose restart fastapi

# Investigate specific module
# Each module logs errors to stdout
docker logs maestroflow-fastapi-1 | grep -i "memory_tracking"
```

---

## Phase 4: Alerts, Dashboards & SLO (Week 4)

### Objective
Deploy alerting and visualization:
- AlertManager configured for Slack/PagerDuty
- Grafana dashboards created
- SLOs defined and monitored
- Runbooks published

### Deployment

#### Pre-Phase 4 Validation
```bash
# 1. All previous phases stable for 7+ days
# 2. Grafana dashboards created and tested
# 3. AlertManager configuration reviewed
# 4. SLOs defined with team input
# 5. Runbooks written and reviewed

# 6. Alert rules validated
python scripts/validate_prometheus_config.py
python scripts/validate_grafana_dashboards.py
```

#### Staging Deployment
```bash
# 1. Deploy AlertManager
docker-compose up -d alertmanager

# 2. Configure notification channels
# - Slack webhook: export SLACK_WEBHOOK_URL="https://..."
# - PagerDuty key: export PAGERDUTY_KEY="..."

# 3. Test alert firing
# Temporarily set thresholds low to trigger alerts
# Edit: monitoring/prometheus/alerts.yml
# Change: memory_usage_high to > 100 MB (instead of 500 MB)

# 4. Restart Prometheus with low thresholds
docker-compose restart prometheus

# 5. Generate load to trigger alerts
python benchmark.py --duration=60

# 6. Verify alerts fire
# Check Slack/PagerDuty for notifications
# Check AlertManager: http://localhost:9093

# 7. Restore normal thresholds
# Edit: monitoring/prometheus/alerts.yml
# Restore original thresholds
docker-compose restart prometheus

# 8. Deploy Grafana dashboards
# Create dashboards via UI and export as JSON
# Or use provisioned dashboards from monitoring/grafana/dashboards/
```

### Success Criteria for Phase 4
- ✅ Alerts fire and notify correctly
- ✅ Grafana dashboards display live data
- ✅ SLOs tracked and displayed
- ✅ Runbooks accessible and actionable
- ✅ Team trained on observability system

---

## Configuration Flags for Gradual Rollout

### Phase 1 Environment Variables
```bash
# Phase 1: Metrics & Health Checks
METRICS_ENABLED=true
PROMETHEUS_PORT=9090
HEALTH_CHECK_INTERVAL_SECONDS=30
MEMORY_THRESHOLD_MB=500
DB_POOL_MAX_SIZE=10
DB_POOL_IDLE_TIMEOUT_SECONDS=300

# Phase 1: Disable everything else
LANGFUSE_ENABLED=false
MEMORY_TRACKING_ENABLED=false
QUEUE_TRACKING_ENABLED=false
CACHE_TRACKING_ENABLED=false
ADVANCED_MONITORING_ENABLED=false
```

### Phase 2 Environment Variables
```bash
# Phase 2: Add Langfuse (gradual sampling)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY="pk_xxx"
LANGFUSE_SECRET_KEY="sk_xxx"
LANGFUSE_HOST="https://cloud.langfuse.com"
LANGFUSE_SAMPLE_RATE=0.1  # Start with 10%
LANGFUSE_TIMEOUT_SECONDS=10

# Phase 2: Keep Phase 1 settings
METRICS_ENABLED=true
PROMETHEUS_PORT=9090

# Phase 2: Disable advanced monitoring
MEMORY_TRACKING_ENABLED=false
QUEUE_TRACKING_ENABLED=false
CACHE_TRACKING_ENABLED=false
```

### Phase 3 Environment Variables
```bash
# Phase 3: Enable advanced monitoring
MEMORY_TRACKING_ENABLED=true
MEMORY_GROWTH_RATE_THRESHOLD_MB_MIN=1
QUEUE_TRACKING_ENABLED=true
QUEUE_DEPTH_ALERT_THRESHOLD_PERCENT=80
CACHE_TRACKING_ENABLED=true
CACHE_HIT_RATIO_ALERT_THRESHOLD_PERCENT=75

# Phase 3: Increase Langfuse sample rate
LANGFUSE_SAMPLE_RATE=1.0  # 100% after validation

# Phase 3: Keep other settings
METRICS_ENABLED=true
LANGFUSE_ENABLED=true
ADVANCED_MONITORING_ENABLED=true
```

### Phase 4 Environment Variables
```bash
# Phase 4: Production-ready configuration
METRICS_ENABLED=true
LANGFUSE_ENABLED=true
LANGFUSE_SAMPLE_RATE=0.5  # 50% in production (balance cost/detail)
MEMORY_TRACKING_ENABLED=true
QUEUE_TRACKING_ENABLED=true
CACHE_TRACKING_ENABLED=true
ADVANCED_MONITORING_ENABLED=true

# Add alerting configuration
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx"
PAGERDUTY_KEY="pdxxxxx"
```

---

## Deployment Checklist

### Pre-Deployment (Each Phase)
- [ ] Code reviewed and approved
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Docker image builds successfully
- [ ] Configuration validated
- [ ] Credentials configured (if needed)
- [ ] Rollback plan documented

### Deployment Day
- [ ] Schedule: Off-peak hours (weekends, nights)
- [ ] Communication: Notify team of deployment
- [ ] Backup: Snapshot current state
- [ ] Monitoring: Alert rules set and verified
- [ ] Documentation: Updated with deployment details

### Post-Deployment (24+ hours)
- [ ] Monitor error rate (should be < 0.1%)
- [ ] Monitor latency (should not increase > 10%)
- [ ] Monitor memory (should be stable)
- [ ] Check Slack/alerts for issues
- [ ] Team standup: Discuss observations
- [ ] Document any issues and fixes

### Success Sign-Off
- [ ] No critical issues detected
- [ ] Success criteria met
- [ ] Team confidence high
- [ ] Ready to proceed to next phase

---

## Communication Plan

### Status Broadcasts
```
Start of Phase 1:
"Phase 1 rollout begins Monday. Expected completion: Friday.
 Observability will be minimal during this period.
 Status updates daily at 10am PT in #observability."

Mid-Phase:
"Phase 1 progressing well. 99.8% uptime, metrics flowing to Prometheus.
 No customer impact observed. Proceeding as planned."

End of Phase:
"Phase 1 complete! Prometheus now collecting 50+ metrics.
 Ready for Phase 2 (Langfuse tracing) starting next Monday.
 Presentation of metrics at Thursday All-Hands."
```

### Escalation Path
```
Severity 1 (Critical):
- App down or 500 errors > 5%
- Action: Rollback immediately
- Notify: On-call lead + team

Severity 2 (High):
- Latency increase > 20%
- Memory growing > 5 MB/min
- Action: Disable new component, investigate
- Notify: Team slack channel

Severity 3 (Medium):
- Latency increase 5-20%
- Memory growing 1-5 MB/min
- Action: Reduce sample rate or disable feature flag
- Notify: #observability channel

Severity 4 (Low):
- Warnings or errors in logs
- Metrics not appearing
- Action: Investigate, document, defer to next phase
```

---

## Success Metrics

### Phase 1 Success
- 99.9% health endpoint uptime
- Prometheus scrape success rate > 99.9%
- Zero observability-related customer impact
- Team comfortable with metrics infrastructure

### Phase 2 Success
- 99.5% Langfuse API success rate
- 10s latency from event to trace visibility
- Request correlation working (trace_id matching)
- Team using traces for debugging

### Phase 3 Success
- Advanced metrics accurate within 5%
- Memory tracking triggering appropriate alerts
- Queue/cache metrics actionable
- Team adjusting configs based on insights

### Phase 4 Success
- Alerts reaching teams 100% of time
- Runbooks used to resolve > 80% of issues
- SLOs > 99% attainment
- Observability system runs autonomously

---

## Next Steps After Rollout

1. **Optimization** (Weeks 5-8)
   - Tune alert thresholds based on production behavior
   - Optimize Langfuse sampling rate
   - Create team-specific dashboards

2. **Automation** (Weeks 9-12)
   - Auto-scaling based on queue depth
   - Automated incident response
   - Cost optimization based on metrics

3. **Analytics** (Weeks 13+)
   - Trend analysis for capacity planning
   - Customer behavior insights from traces
   - Performance optimization recommendations
