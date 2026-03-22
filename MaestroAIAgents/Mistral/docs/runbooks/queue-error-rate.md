---
type: runbook
title: Queue Error Rate High - Runbook
created: 2026-03-21
tags:
  - queue
  - errors
  - reliability
  - observability
---

# Alert: Queue Error Rate Exceeds Threshold

## Description

This alert fires when queue task error rate exceeds **5%** for 5 minutes, indicating tasks are failing faster than expected. This threatens data consistency and SLA compliance.

**Alert Level:** CRITICAL

---

## Likely Causes

1. **External Service Failure**
   - API dependency down or returning errors
   - Database connection issues
   - Third-party service unavailable

2. **Application Bug**
   - Recent deployment with regression
   - Unhandled exception in task processing
   - Type mismatch or validation error

3. **Invalid Task Payload**
   - Malformed message format
   - Missing required fields
   - Incompatible data type

4. **Resource Exhaustion**
   - Out of memory exceptions
   - Disk quota exceeded
   - Database connection pool exhausted

5. **Cascading Failures**
   - One task failure triggering others
   - Dead-letter queue growing
   - Retry logic causing pile-up

---

## Troubleshooting

### 1. Check Error Rate and Trend
```bash
# Query current error rate
curl http://localhost:8000/metrics | grep queue_error_rate

# Expected: < 5%
# If > 10%: Critical situation
```

### 2. Identify Failing Task Types
```bash
# Query logs for errors by task type
grep "task failed" /var/log/maestroflow.log | cut -d: -f3 | sort | uniq -c | sort -rn | head -10

# Or check metrics by queue name
curl http://localhost:8000/metrics | grep "queue_errors_total"
```

### 3. Examine Error Messages
```bash
# Get recent failure logs
tail -100 /var/log/maestroflow.log | grep -i error

# Look for patterns:
# - Connection refused → External service down
# - Validation error → Bad payload
# - Out of memory → Resource issue
# - Timeout → External service slow
```

### 4. Check Dead-Letter Queue
```bash
# See how many tasks are in DLQ
curl http://localhost:8000/metrics | grep queue_dlq_messages_total

# If growing rapidly: Tasks failing and being retried too many times
```

### 5. Review Recent Deployments
```bash
# Check git log for recent changes
git log --oneline -20

# Check if error spike correlates with deployment
# Use timestamps to cross-reference logs
```

### 6. Test External Dependencies
```bash
# Check API availability
curl -I https://api.external-service.com/health

# Check database connectivity
nc -zv database.internal 5432

# Check other services
redis-cli ping
```

---

## Resolution

**If External Service Down:**
- Check status page: https://status.external-service.com
- Wait for recovery or switch to backup service
- Implement circuit breaker to fail fast:
  ```python
  @circuit_breaker(failure_threshold=5, timeout=60)
  def call_external_api():
      # API call
      pass
  ```

**If Recent Deployment Issue:**
```bash
# Revert to previous version
git revert HEAD
docker-compose restart worker

# Or rollback deployment
kubectl rollout undo deployment/maestroflow-worker
```

**If Invalid Payloads:**
- Check message format in source application
- Add validation logging to identify payload mismatches
```python
try:
    task = parse_task(payload)
except ValidationError as e:
    logger.error(f"Invalid payload: {e}, payload={payload}")
    # Send to DLQ or manual review queue
```

**If Resource Exhaustion:**
```bash
# Increase resource limits
# For containers:
docker-compose up -d --memory=2g worker

# For Kubernetes:
kubectl set resources deployment maestroflow-worker --requests=memory=1Gi --limits=memory=2Gi

# Scale down if over capacity:
docker-compose down
docker-compose up -d --scale worker=5  # Reduce workers
```

**If Cascading Failures:**
- Increase max retries with exponential backoff
```python
@retry(max_attempts=3, backoff_seconds=2)
def process_task(task):
    # Processing logic
    pass
```
- Limit concurrent retry attempts
- Add task priority queue

---

## Escalation and Monitoring

**If Error Rate Stays > 5% After 5 Minutes:**
1. Page on-call engineer
2. Invoke incident response protocol
3. Prepare customer communication

**Monitor:**
- Error rate trending down after fix
- DLQ draining (errors being resolved)
- No new error types appearing

**Success Criteria:**
- Error rate < 1% for 5 minutes
- DLQ stable (not growing)
- All external dependencies responding
- No red flags in logs

---

## Prevention

- Add validation on task payload at queue entry point
- Implement circuit breakers for external service calls
- Set task timeouts to prevent hangs
- Monitor external dependencies health continuously
- Test failure scenarios in staging environment
- Maintain runbook of external service SLAs
- Set up alerts for DLQ growth rate
- Require load testing before deployments affecting task processing
