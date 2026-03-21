## Langfuse Dashboards & Monitoring Guide

This document describes recommended Langfuse dashboard queries and configurations for monitoring MaestroFlow's observability.

### Prerequisites

- Langfuse instance configured and connected to MaestroFlow
- Traces flowing from MaestroFlow to Langfuse (verify via `/api/health/langfuse` endpoint)
- Dashboard access in Langfuse web UI

---

## Key Dashboards & Queries

### 1. LLM Call Latency by Model

**Purpose:** Monitor inference latency trends across different LLM providers.

**Query:**
```
Trace type: LLM Call
Group by: model
Metric: duration (P50, P95, P99)
Filter: status = "success"
Time range: Last 24 hours (configurable)
```

**Use case:** Detect performance degradation in specific models or identify slower models for cost/latency trade-offs.

---

### 2. Error Rate by Endpoint

**Purpose:** Track which endpoints are experiencing the highest error rates.

**Query:**
```
Trace type: HTTP Request
Group by: endpoint
Metric: error_count / total_count = error_rate
Filter: status != "200"
Time range: Last 24 hours
```

**Use case:** Prioritize bug fixes and investigation for high-error endpoints.

---

### 3. Database Query Latency Distribution

**Purpose:** Monitor database query performance and identify slow queries.

**Query:**
```
Trace type: Database Query
Group by: query_type (SELECT, INSERT, UPDATE, DELETE)
Metric: duration (P50, P95, P99)
Filter: duration > 100ms (slow query threshold)
Time range: Last 7 days
```

**Use case:** Identify N+1 queries, missing indexes, or connection pool issues.

---

### 4. Request Trace Timeline

**Purpose:** View end-to-end request flow with all child spans (LLM calls, DB queries, etc.).

**Query:**
```
Trace ID: (user-provided from error response or logs)
View: Timeline
Show: All spans with durations and status
```

**Example trace flow:**
```
HTTP GET /api/analyze (150ms total)
  ├─ Initialize context (1ms)
  ├─ LLM Call - gpt-4 (120ms)
  │  ├─ Send prompt (5ms)
  │  └─ Stream response (115ms)
  ├─ Database Query - INSERT (20ms)
  └─ Finalize response (9ms)
```

**Use case:** Debug end-to-end request failures, identify bottlenecks.

---

### 5. LLM Cost Breakdown by Model

**Purpose:** Track spending across different LLM providers and models.

**Query:**
```
Trace type: LLM Call
Group by: model
Metric: sum(cost_usd)
Filter: None
Time range: Last 30 days
Sort by: cost_usd DESC
```

**Example output:**
```
gpt-4:         $1,245.32 (45%)
claude-3-opus: $  890.15 (32%)
gpt-3.5-turbo: $  542.08 (20%)
mistral-7b:    $   47.22 (2%)
```

**Use case:** Identify cost-saving opportunities, budget tracking, capacity planning.

---

### 6. Request Volume & Throughput

**Purpose:** Monitor API request volume and throughput trends.

**Query:**
```
Trace type: HTTP Request
Metric: request_count
Group by: time bucket (1 hour)
Filter: endpoint contains "/api/"
Time range: Last 7 days
```

**Use case:** Detect traffic spikes, plan capacity scaling.

---

### 7. Langfuse Event Queue Health

**Purpose:** Monitor the Langfuse circuit breaker and event queue status.

**Metrics to watch:**
- `langfuse_event_queue_depth` — current queued events (should be ~0 when healthy)
- `langfuse_circuit_breaker_state` — "closed" (healthy) or "open" (degraded)
- `langfuse_circuit_breaker_failures` — cumulative failure count

**Use case:** Detect observability degradation or Langfuse API outages.

---

### 8. Exception Rate Over Time

**Purpose:** Track exception trends and identify new error spikes.

**Query:**
```
Trace type: Exception
Group by: exception_type
Metric: count
Filter: None
Time range: Last 7 days
```

**Example output:**
```
ValueError:        42 (30%)
TimeoutError:      35 (25%)
ConnectionError:   28 (20%)
RuntimeError:      25 (18%)
```

**Use case:** Identify emerging issues, correlate with deployments or external service changes.

---

## Filtering & Navigation

### Filter by Trace ID

In error responses (via `ErrorTracer.get_error_context_for_response()`), the `trace_id` is included. Users or support can paste this trace ID into Langfuse to view the complete request:

```json
{
  "error": "ValueError",
  "message": "Invalid configuration",
  "trace_id": "trace_abc123def456"
}
```

Copy `trace_id` → Paste into Langfuse search → View full timeline.

### Filter by User ID

If user authentication is enabled, Langfuse traces include `user_id` in metadata:

```
Search: user_id = "user_12345"
Result: All traces for that user (request history, error patterns, usage)
```

### Filter by Session ID

For session-scoped analysis:

```
Search: session_id = "sess_xyz789"
Result: All traces within a user session (conversation flow, decision points)
```

---

## Setting Up Custom Dashboards

Langfuse supports creating custom dashboards with widgets (charts, tables, metrics).

### Recommended Dashboard: "System Health Overview"

**Widgets:**
1. **LLM Cost Today** (gauge) — `sum(llm_cost_usd) where timestamp > today`
2. **Error Rate Last Hour** (line chart) — error_count / total_count over time
3. **P99 Latency** (gauge) — `max(duration) at P99` across all endpoints
4. **Database Slow Queries** (table) — queries with `duration > 100ms`, sorted by count
5. **Langfuse Queue Depth** (gauge) — `langfuse_event_queue_depth`
6. **Active Requests** (counter) — real-time request count (requires streaming)

---

## Alerting (Optional)

Langfuse supports webhook alerts. Configure alerts for:

- **High Error Rate:** If `error_rate > 5%` for 5 minutes
- **High Latency:** If `P95 latency > 2s` for 10 minutes
- **Langfuse Circuit Open:** If `circuit_breaker_state == "open"`
- **Unexpected Cost Spike:** If `daily_cost > baseline * 1.5`

Example webhook payload:

```json
{
  "alert_name": "High Error Rate",
  "condition": "error_rate > 5%",
  "current_value": "7.2%",
  "timeframe": "last_5_minutes",
  "timestamp": "2024-03-21T15:30:00Z",
  "action": "POST to your-slack-webhook-url"
}
```

---

## Troubleshooting

### No traces appearing in Langfuse

1. Verify `LANGFUSE_ENABLED=true` and credentials are set
2. Check `/api/health/langfuse` endpoint returns healthy status
3. Ensure Langfuse public/secret keys are correct
4. Check network connectivity from MaestroFlow to Langfuse host
5. Review MaestroFlow logs for `ERROR` in observability module

### Traces missing LLM calls

- Verify `@trace_llm_call` decorator is applied to LLM wrapper functions
- Check that `initialize_request_context()` is called in middleware (should auto-happen)
- Verify `LANGFUSE_SAMPLE_RATE` is > 0 (default 1.0 = trace everything)

### Circuit breaker frequently opening

- Check Langfuse API health and latency
- Verify network connectivity to Langfuse host
- Reduce `LANGFUSE_TIMEOUT_SECONDS` if set too high (default 5s)
- Review Langfuse rate limits if high volume of requests

---

## References

- [Langfuse Documentation](https://langfuse.com/docs)
- [Langfuse API Reference](https://api.reference.langfuse.com)
- [MaestroFlow Observability Config](../src/config/observability.py)
