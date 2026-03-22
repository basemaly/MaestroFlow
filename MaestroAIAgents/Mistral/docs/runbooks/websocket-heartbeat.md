---
type: runbook
title: WebSocket Heartbeat Failures - Runbook
created: 2026-03-21
tags:
  - websocket
  - connectivity
  - health
  - observability
---

# Alert: WebSocket Heartbeat Failures

## Description

This alert fires when WebSocket heartbeat (ping/pong) failures exceed threshold on a given endpoint, indicating connections are becoming unstable or becoming stale.

**Alert Level:** WARNING

---

## Likely Causes

1. **Client Network Issues**
   - High latency on client connection
   - Unreliable network (WiFi, cellular)
   - Packet loss > 5%

2. **Server Capacity Issues**
   - High CPU load preventing timely pong response
   - Memory pressure causing response delays
   - Thread pool exhausted

3. **Firewall/Proxy Issues**
   - Connection timeout in middle proxy
   - Firewall dropping idle connections
   - Load balancer timeout too aggressive

4. **Application Bug**
   - Message handler blocking pong sending
   - Exception in pong handler
   - Deadlock or resource contention

5. **Browser/Client Limits**
   - Browser closing idle connections
   - Mobile browser network optimization
   - Client-side timeout too short

---

## Troubleshooting

### 1. Check Heartbeat Failure Metrics
```bash
# Query heartbeat failures
curl http://localhost:8000/metrics | grep websocket_heartbeat_failures_total

# Check by endpoint to identify problem areas
```

### 2. Review Connection Durations
```bash
# Check how long connections are staying open
curl http://localhost:8000/metrics | grep websocket_connection_duration_seconds

# If many connections < 5 minutes: Possibly heartbeat timeout
# Expected: Connections should last hours unless user closes
```

### 3. Monitor Server Resource Usage
```bash
# Check CPU and memory during heartbeat timeouts
docker stats
top -b -n 1

# Check thread pool status
curl http://localhost:8000/metrics | grep thread

# If any maxed out: Resource pressure likely cause
```

### 4. Analyze Connection Logs
```bash
# Look for heartbeat-related logs
tail -500 /var/log/maestroflow.log | grep -i heartbeat

# Check for patterns:
# - Failed pong response
# - Timeout waiting for pong
# - Connection closed after N failures
```

### 5. Check Network Connectivity
```bash
# Simulate network latency
ping -c 10 $(dig +short client_ip)

# Check TCP connection state
netstat -an | grep ESTABLISHED | wc -l

# Look for CLOSE_WAIT state (indicates unclean closure):
netstat -an | grep CLOSE_WAIT | wc -l
```

### 6. Test Heartbeat Manually
```bash
# Create test connection
wscat -c ws://localhost:8000/ws/test

# Monitor packets (in another terminal):
tcpdump -i lo 'port 8000' -X

# Should see ping/pong frames periodically
```

---

## Resolution

**If Client Network Issues:**
- Request client network diagnostics
- Ask user to test from different network (home vs office)
- May be temporary; recommend user reconnect if stable afterward
- Increase heartbeat timeout if network is consistently slow:
  ```python
  HEARTBEAT_TIMEOUT_SECONDS = 45  # Increase from 30
  ```

**If Server Capacity Issue:**
```bash
# Check CPU/memory in detail
top -p $(pgrep -d',' -f 'python.*ws')

# If CPU high:
# 1. Profile application: python -m cProfile app.py
# 2. Optimize hot code paths
# 3. Scale horizontally (add more servers)

# If memory high:
# 1. Check for memory leaks: memory_profiler
# 2. Increase container memory limits
# 3. Reduce connection pool size if it's growing unbounded
```

**If Firewall/Proxy Issues:**
- Work with DevOps to review firewall/proxy settings
- Increase idle timeout on intermediate proxies:
  ```
  # nginx.conf or similar
  proxy_read_timeout 300s;
  ```
- Reduce heartbeat interval to keep connection "warm":
  ```python
  HEARTBEAT_INTERVAL_SECONDS = 15  # Decrease from 30
  ```

**If Application Bug:**
```bash
# Review recent WebSocket handler changes
git log --oneline -10 -- backend/src/api/websocket.py

# Check for blocking operations in handler:
# - Long database queries
# - External API calls without timeout
# - Lock contention

# Add timeout to handler:
@timeout(seconds=5)
async def handle_message(ws, message):
    # Handler logic
    pass

# Restart worker:
docker-compose restart
```

**If Browser/Client Limits:**
- Check WebSocket client library documentation
- Some browsers/libraries drop connections after inactivity
- May need to reduce heartbeat interval on client side
- Upgrade client library to latest version

---

## Adjusting Heartbeat Parameters

**Heartbeat Too Aggressive (too frequent):**
```python
# Current settings causing too many failures
HEARTBEAT_INTERVAL_SECONDS = 30  # How often to send ping
HEARTBEAT_TIMEOUT_SECONDS = 10    # Wait for pong response
MAX_HEARTBEAT_FAILURES = 3        # Disconnect after 3 failures

# Adjust to be more lenient:
HEARTBEAT_INTERVAL_SECONDS = 45
HEARTBEAT_TIMEOUT_SECONDS = 20
MAX_HEARTBEAT_FAILURES = 5
```

**Heartbeat Too Lenient (not catching dead connections):**
```python
# Make more aggressive to detect dead connections faster
HEARTBEAT_INTERVAL_SECONDS = 15
HEARTBEAT_TIMEOUT_SECONDS = 5
MAX_HEARTBEAT_FAILURES = 2
```

---

## Verification

**After Adjustments:**
- Monitor heartbeat failure rate for 30 minutes
- Should drop significantly if timeout was wrong
- Watch for over-correction (too lenient → no dead connection detection)

**Success Criteria:**
- Heartbeat failure rate < 1% (occasional network hiccups OK)
- Connections staying open for expected duration
- No increase in unexplained disconnects

---

## Prevention

- Monitor heartbeat failures continuously
- Set heartbeat parameters based on client network expectations
- Test from various networks (WiFi, cellular, VPN)
- Document heartbeat configuration in client API docs
- Implement exponential backoff for failed heartbeats
- Alert on heartbeat failures to catch issues early
- Regular review of connection durations vs expected
