---
type: runbook
title: WebSocket Error Rate High - Runbook
created: 2026-03-21
tags:
  - websocket
  - connectivity
  - errors
  - observability
---

# Alert: WebSocket Error Rate Exceeds Threshold

## Description

This alert fires when WebSocket error rate exceeds **5%** for 5 minutes, indicating clients are experiencing message handling failures or connection errors.

**Alert Level:** WARNING

---

## Likely Causes

1. **Message Parsing Errors**
   - Client sending invalid JSON or message format
   - Protocol version mismatch
   - Encoding issues (UTF-8 expected, other encoding sent)

2. **Handler Exception**
   - Bug in message handler code
   - Recent deployment with regression
   - Unhandled edge case

3. **Resource Pressure**
   - Out of memory errors
   - Connection pool exhausted
   - CPU spike causing timeouts

4. **Network Issues**
   - High latency causing timeouts
   - Packet loss causing retransmissions
   - Connection resets

5. **Client-Side Issues**
   - Browser/client bugs
   - Malformed message construction
   - Incompatible client version

---

## Troubleshooting

### 1. Check Error Metrics by Endpoint
```bash
# Query WebSocket errors by endpoint
curl http://localhost:8000/metrics | grep websocket_errors_total

# Look for specific endpoints with high error rates
# Example output:
# websocket_errors_total{endpoint="/ws/chat", error_type="JSONDecodeError"} 42
```

### 2. Analyze Error Types
```bash
# Check logs for error patterns
tail -200 /var/log/maestroflow.log | grep websocket | grep error

# Common error types to look for:
# - JSONDecodeError: Invalid JSON from client
# - ValueError: Message validation failed
# - TimeoutError: Handler took too long
# - ConnectionError: Unexpected disconnect
```

### 3. Check Specific Endpoints
```bash
# If /ws/chat has high errors:
# 1. Check handler code in backend/src/api/websocket.py
# 2. Review recent changes to that endpoint
# 3. Check if specific message types cause issues

# Query by message type if available:
grep "chat" /var/log/maestroflow.log | grep error | head -20
```

### 4. Monitor Resource Usage
```bash
# Check memory and CPU
docker stats
ps aux | grep python | head -5

# Check connection pool
curl http://localhost:8000/metrics | grep "websocket_connections_active"

# If approaching limits: May indicate resource pressure
```

### 5. Analyze Client Patterns
```bash
# Check which clients are causing errors
tail -500 /var/log/maestroflow.log | grep "websocket" | grep -E "client_id|user_id" | head -20

# Look for specific users/clients with high error rates
# May indicate client-side bug or incompatibility
```

### 6. Test Manual Message Send
```bash
# Create test WebSocket connection
# Use wscat or similar tool:
wscat -c ws://localhost:8000/ws/chat

# Send test message and see if error occurs
{"type": "message", "text": "hello"}

# If error: Log the exact error for investigation
```

---

## Resolution

**If JSON/Format Errors:**
- Check client code for message construction
- Add logging of raw message bytes in handler:
  ```python
  try:
      data = json.loads(raw_message)
  except JSONDecodeError as e:
      logger.error(f"Invalid JSON from {client_id}: {raw_message[:200]}")
      await send_error_response("Invalid message format")
      return
  ```
- May indicate version mismatch; check API docs with client team

**If Handler Exception:**
```bash
# Review recent commits to WebSocket handler
git log --oneline -10 -- backend/src/api/websocket.py

# Revert if regression found:
git revert <commit-hash>
docker-compose restart

# Or fix the bug:
# 1. Add try-catch around handler logic
# 2. Log full stack trace for debugging
# 3. Send error response to client
```

**If Resource Pressure:**
```bash
# Increase container resources
docker-compose down
# Edit docker-compose.yml to increase memory limit

# Or for Kubernetes:
kubectl set resources deployment maestroflow --requests=memory=2Gi --limits=memory=4Gi

# Restart
docker-compose up -d
```

**If Network Issues:**
- Check latency: `ping client_ip`
- Run packet capture: `tcpdump -i eth0 'port 8000'`
- May be transient; monitor for continued errors

**If Client Issue:**
- Request client logs from affected users
- Ask them to upgrade client/browser
- Test with different client versions
- Set up compatibility matrix

---

## Verification

**Monitor After Fix:**
- Error rate should drop to < 1% within 5 minutes
- Check specific endpoint that had errors
- Verify no new error types appearing

**Success Criteria:**
- Error rate < 1% for 5 minutes
- All WebSocket endpoints functioning
- Error logs show no stack traces (graceful handling)

---

## Prevention

- Validate all message formats at entry point
- Add comprehensive error handling with logging
- Implement message version field for compatibility
- Test with multiple client implementations
- Monitor error rate continuously
- Set up alerts for new error types
- Document expected message formats for clients
- Test error scenarios in staging (malformed messages, etc.)
