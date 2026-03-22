---
type: report
title: Documentation Fix Plan - Loop 00001
created: 2026-03-21
tags:
  - mozart-analysis
  - documentation-plan
  - maestroflow
related:
  - '[[LOOP_00001_GAPS]]'
  - '[[LOOP_00001_FEATURE_INVENTORY]]'
---

# Documentation Fix Plan - Loop 00001

## Summary
- **Total Gaps:** 14
- **Auto-Fix (PENDING):** 10
- **Needs Review:** 1
- **Won't Do:** 3

## Current README Accuracy: 0%
## Target README Accuracy: 90%

---

## PENDING - Ready for Auto-Fix

### DOC-001: Circuit Breaker Pattern
- **Status:** `IMPLEMENTED`
- **Implemented In:** Loop 00001
- **Gap ID:** GAP-001
- **Type:** MISSING
- **User Importance:** CRITICAL
- **Fix Effort:** MEDIUM
- **README Section:** Core Concepts / Architecture
- **Fix Description:**
  Document the Circuit Breaker pattern as the foundation of Mozart's resilience strategy. Explain the state machine (CLOSED → OPEN → HALF_OPEN), configuration parameters, and how threshold/timeout values affect behavior. Include examples of different failure scenarios.
- **Proposed Content:**
  ```markdown
  ### Circuit Breaker Pattern
  
  Mozart uses the **Circuit Breaker pattern** to implement fail-fast behavior and prevent cascading failures. The circuit breaker monitors request success/failure rates and automatically "opens" (stops forwarding requests) when failure thresholds are exceeded.
  
  #### States
  - **CLOSED:** Normal operation, all requests forwarded
  - **OPEN:** Too many failures detected, requests rejected immediately with circuit error
  - **HALF_OPEN:** Testing if service recovered, limited requests allowed through
  
  #### Key Configuration
  - `failure_threshold`: Number of failures before opening (default: 5)
  - `success_threshold`: Successful requests needed to close from HALF_OPEN (default: 2)
  - `timeout`: Request timeout in seconds (default: 30s)
  - `reset_timeout`: Time before attempting recovery from OPEN state (default: 60s)
  
  This prevents your application from overwhelming a degraded service and allows time for recovery.
  ```

### DOC-002: HTTP Client Manager
- **Status:** `IMPLEMENTED`
- **Implemented In:** Loop 00001
- **Gap ID:** GAP-004
- **Type:** MISSING
- **User Importance:** CRITICAL
- **Fix Effort:** MEDIUM
- **README Section:** Getting Started / Usage
- **Fix Description:**
  Document how to initialize and use the HTTPClientManager singleton. List the 8 managed services, explain when to use the client manager vs direct HTTP, and show basic initialization code.
- **Proposed Content:**
  ```markdown
  ## HTTP Client Manager
  
  Mozart provides a centralized **HTTPClientManager** for managing HTTP requests to external services with built-in circuit breaking, connection pooling, and health checks.
  
  ### Managed Services
  Mozart monitors and protects requests to:
  - **SurfSense** — Web scraping/data extraction
  - **LiteLLM** — LLM API routing (High-Cost protection)
  - **Langfuse** — Observability logging
  - **LangGraph** — Agent framework integration
  - **OpenViking** — Custom data source
  - **ActivePieces** — Workflow automation
  - **BrowserRuntime** — Browser automation
  - **StateWeave** — State management service
  
  ### Usage
  ```python
  from mozart.http_client_manager import HTTPClientManager, ServiceName
  
  manager = HTTPClientManager()
  # GET request with circuit breaker protection
  response = manager.get(ServiceName.SURFSENSE, "https://api.surfsense.io/data")
  ```
  
  Each service has pre-configured resilience settings optimized for its characteristics.
  ```

### DOC-003: Dynamic Executor Pool
- **Status:** `IMPLEMENTED`
- **Implemented In:** Loop 00001
- **Gap ID:** GAP-003
- **Type:** MISSING
- **User Importance:** CRITICAL
- **Fix Effort:** MEDIUM
- **README Section:** Core Concepts
- **Fix Description:**
  Explain the auto-scaling executor pool that manages subagent execution. Document how worker count adjusts based on queue depth and system resources, min/max worker bounds, and graceful shutdown behavior.
- **Proposed Content:**
   ```markdown
   ### Dynamic Executor Pool
   
   Mozart automatically manages a pool of worker threads to execute subagents concurrently. The pool size adjusts dynamically based on:
   - Queue depth (pending tasks)
   - System resource availability (CPU, memory)
   - Configured min/max bounds
   
   #### Default Configuration
   - **Min workers:** 2 (always available for low-latency execution)
   - **Max workers:** 16 (prevents resource exhaustion)
   
   The pool handles:
   - **Backpressure:** Rejects new tasks when all workers are busy
   - **Graceful shutdown:** Completes pending tasks before terminating
   - **Resource monitoring:** Tracks CPU/memory per task and pool-wide
   
   This ensures Mozart scales efficiently with demand while protecting system stability.
   ```

### DOC-004: Metrics Collection System
- **Status:** `PENDING`
- **Gap ID:** GAP-008
- **Type:** MISSING
- **User Importance:** HIGH
- **Fix Effort:** MEDIUM
- **README Section:** Monitoring & Observability
- **Fix Description:**
  Document the built-in metrics system that tracks requests, responses, state changes, and resource usage. Explain what metrics are available and how to access them for production monitoring.
- **Proposed Content:**
  ```markdown
  ## Metrics & Observability
  
  Mozart collects comprehensive metrics on circuit breaker behavior and executor pool performance.
  
  ### Circuit Breaker Metrics
  - **Request counts:** total, successful, failed, rejected, timeout
  - **Response times:** min, max, average (milliseconds)
  - **State changes:** history with timestamps
  - **Pool status:** connection count, health status
  
  ### Executor Pool Metrics
  - **Task status breakdown:** pending, running, completed, failed
  - **Queue metrics:** wait times from submission to execution
  - **Execution times:** per-task duration distribution
  - **Resource usage:** CPU percentage, memory percentage
  
  Metrics are maintained in a sliding window (default: last 100 events) for performance.
  
  ### Accessing Metrics
  ```python
  circuit_breaker = manager.get_circuit_breaker(ServiceName.SURFSENSE)
  metrics = circuit_breaker.metrics
  
  print(f"Success rate: {metrics.successful}/{metrics.total}")
  print(f"Avg response time: {metrics.average_response_time}ms")
  ```
  ```

### DOC-005: Graceful Shutdown
- **Status:** `PENDING`
- **Gap ID:** GAP-005
- **Type:** MISSING
- **User Importance:** HIGH
- **Fix Effort:** EASY
- **README Section:** Deployment / Production
- **Fix Description:**
  Document how Mozart handles graceful shutdown via signal handlers (SIGTERM/SIGINT) and atexit hooks. Explain the timeout for task completion and what happens when it expires.
- **Proposed Content:**
  ```markdown
  ### Graceful Shutdown
  
  Mozart handles shutdown gracefully through signal handlers and cleanup hooks:
  
  - **SIGTERM/SIGINT:** Initiates graceful shutdown, allows in-flight tasks to complete
  - **Task completion timeout:** Default 30 seconds to finish pending tasks
  - **Force termination:** After timeout, remaining tasks are cancelled
  - **Resource cleanup:** Connections and executor pools closed properly
  
  This is essential for Kubernetes and Docker deployments to prevent request loss.
  ```

### DOC-006: Multi-Service Management
- **Status:** `PENDING`
- **Gap ID:** GAP-009
- **Type:** MISSING
- **User Importance:** HIGH
- **Fix Effort:** MEDIUM
- **README Section:** Configuration
- **Fix Description:**
  Document the three service configuration tiers (High-Cost, Critical, Non-Blocking, Standard) and explain why each service has different timeout/retry settings. Show how to understand and customize service configuration.
- **Proposed Content:**
  ```markdown
  ## Service Configuration Tiers
  
  Mozart pre-configures each service based on its cost and criticality:
  
  ### High-Cost Services
  - **LiteLLM** — Expensive LLM API calls
  - Timeout: 60s, Max Retries: 2, Failure Threshold: 3
  - Prevents retrying expensive failed requests too many times
  
  ### Critical Services
  - **SurfSense** — Core data extraction
  - Timeout: 30s, Max Retries: 3, Failure Threshold: 5
  - Tolerates more transient failures due to external factors
  
  ### Non-Blocking Services
  - **Langfuse** — Logging (failures don't block main workflow)
  - Timeout: 5s, Max Retries: 1, Failure Threshold: 10
  - Fast failure to prevent delays from non-critical services
  
  ### Standard Services
  - Default timeouts and retry counts for other services
  
  Configuration is automatically applied through HTTPClientManager.
  ```

### DOC-007: Connection Pool Monitoring
- **Status:** `PENDING`
- **Gap ID:** GAP-002
- **Type:** MISSING
- **User Importance:** MEDIUM
- **Fix Effort:** EASY
- **README Section:** Monitoring & Observability
- **Fix Description:**
  Document how to monitor connection pool health, including pool status endpoints and health check configuration. Brief addition to the monitoring section.
- **Proposed Content:**
  ```markdown
  ### Connection Pool Monitoring
  
  Mozart monitors HTTP connection pool health with per-service tracking:
  
  - **Pool status endpoint:** Available for health checks
  - **Connection limits:** Configurable max connections per service
  - **Keepalive management:** Configurable keepalive limits
  - **Health history:** Timestamps of state changes
  
  Use this for understanding why a service may be degraded or slow.
  ```

### DOC-008: Resource Monitoring
- **Status:** `PENDING`
- **Gap ID:** GAP-006
- **Type:** MISSING
- **User Importance:** MEDIUM
- **Fix Effort:** EASY
- **README Section:** Monitoring & Observability
- **Fix Description:**
  Document system resource tracking (CPU/memory) and how to use metrics to tune pool sizing and detect resource constraints.
- **Proposed Content:**
  ```markdown
  ### System Resource Monitoring
  
  Mozart tracks system-level metrics to prevent resource exhaustion:
  
  - **CPU usage %:** Current system CPU percentage
  - **Memory usage %:** Current system memory percentage
  - **Per-task resources:** CPU and memory consumed by individual tasks
  
  Monitor these metrics to detect when pool sizing needs adjustment or when external load affects Mozart.
  ```

### DOC-009: Exponential Backoff Retry Logic
- **Status:** `PENDING`
- **Gap ID:** GAP-007
- **Type:** MISSING
- **User Importance:** MEDIUM
- **Fix Effort:** EASY
- **README Section:** Core Concepts / Configuration
- **Fix Description:**
  Briefly explain the exponential backoff algorithm used for retries and mention when jitter is applied to prevent thundering herd problems.
- **Proposed Content:**
  ```markdown
  ### Exponential Backoff Retry Strategy
  
  When a request fails, Mozart retries with exponential backoff:
  
  ```
  delay = min(base_delay * (2 ^ retry_count), max_delay)
  ```
  
  - **Base delay:** 1.0 second (attempt 1: 1s, attempt 2: 2s, attempt 3: 4s)
  - **Max delay:** 30 seconds (prevents excessive wait)
  - **Jitter:** Optional randomization to prevent thundering herd
  
  Configure via service-specific settings or circuit breaker config.
  ```

### DOC-010: Graceful Degradation Patterns
- **Status:** `PENDING`
- **Gap ID:** GAP-014
- **Type:** MISSING
- **User Importance:** MEDIUM
- **Fix Effort:** MEDIUM
- **README Section:** Advanced / Patterns
- **Fix Description:**
  Document the multiple degradation strategies available when services fail: cached responses, fallback endpoints, event queuing for replay, and degradation flags. Show how different services use different patterns.
- **Proposed Content:**
  ```markdown
  ## Graceful Degradation Patterns
  
  When a service circuit opens or becomes unavailable, Mozart implements multiple degradation strategies:
  
  ### Cached Responses
  Return previously cached successful responses when the circuit is open. Useful for read-heavy operations.
  
  ### Fallback Endpoints
  Automatically switch to a configured fallback URL for continued operation at reduced capacity.
  ```python
  config.fallback_url = "https://fallback.surfsense.io"
  ```
  
  ### Event Queuing for Replay
  Queue events (e.g., logs, metrics) for replay when service recovers. Example: Langfuse event logging.
  
  ### Degradation Flags
  Return responses with a `degraded=true` flag indicating reduced functionality or stale data.
  
  Choose strategies based on your service's role and the acceptable trade-offs.
  ```

---

## PENDING - NEEDS REVIEW

### DOC-011: Fallback URL Support
- **Status:** `PENDING - NEEDS REVIEW`
- **Gap ID:** GAP-010
- **Type:** MISSING
- **User Importance:** MEDIUM
- **Fix Effort:** MEDIUM
- **Questions:**
  - How are fallback URLs configured per-service? Environment variables, config file, or programmatic?
  - What's the fallback activation logic? Circuit open, timeout, or both?
  - Should we document examples for each managed service?

---

## WON'T DO

### DOC-012: SurfSense Integration Pattern
- **Status:** `WON'T DO`
- **Gap ID:** GAP-012
- **Type:** MISSING
- **Reason:** Service-specific integration pattern. While implementation exists and is well-tested, this is advanced documentation for developers integrating custom services. Document in advanced/integration-patterns.md as a reference example rather than main README. Low immediate impact for general users.

### DOC-013: LiteLLM Cost Protection Pattern
- **Status:** `WON'T DO`
- **Gap ID:** GAP-013
- **Type:** MISSING
- **Reason:** Service-specific tuning example for an advanced use case (protecting expensive API calls). The general circuit breaker documentation (DOC-001) covers the pattern; this is a specialized configuration. Can be documented as an example in advanced docs or as a guide for custom services. Not blocking for baseline README.

### DOC-014: Per-Service Health Checks
- **Status:** `WON'T DO`
- **Gap ID:** GAP-011
- **Type:** MISSING
- **Reason:** Optional monitoring enhancement. Health checking infrastructure exists but is an advanced feature. Document in monitoring.md as optional enhancement rather than core README requirement. Users can adopt after understanding baseline metrics and circuit breaker concepts.

---

## Fix Order

Recommended sequence based on importance and dependencies:

1. **DOC-001** — Circuit Breaker Pattern (CRITICAL, foundation for understanding Mozart)
2. **DOC-002** — HTTP Client Manager (CRITICAL, needed to use the library)
3. **DOC-003** — Dynamic Executor Pool (CRITICAL, core execution model)
4. **DOC-004** — Metrics Collection System (HIGH, essential for production)
5. **DOC-005** — Graceful Shutdown (HIGH, required for production deployment)
6. **DOC-006** — Multi-Service Management (HIGH, explains configuration tiers)
7. **DOC-007** — Connection Pool Monitoring (MEDIUM, monitoring support)
8. **DOC-008** — Resource Monitoring (MEDIUM, monitoring support)
9. **DOC-009** — Exponential Backoff Retry (MEDIUM, understanding retry behavior)
10. **DOC-010** — Graceful Degradation Patterns (MEDIUM, advanced operational patterns)

---

## README Section Updates Needed

| Section | Gaps to Fix | Action Needed |
|---------|-------------|---------------|
| Getting Started / Quick Start | DOC-002 | Add HTTPClientManager initialization example |
| Core Concepts / Architecture | DOC-001, DOC-003 | Document circuit breaker state machine and executor pool auto-scaling |
| Configuration | DOC-006, DOC-009 | Explain service tiers and exponential backoff tuning |
| Monitoring & Observability | DOC-004, DOC-007, DOC-008 | Document metrics access, pool health, resource tracking |
| Deployment / Production | DOC-005 | Explain graceful shutdown behavior for containerized deployments |
| Advanced | DOC-010, DOC-011 | Document degradation patterns and fallback configuration |

---

## Evaluation Rationale

### Critical Gaps (Blocks Basic Usage)
- **DOC-001, DOC-002, DOC-003:** Without these, users cannot understand what Mozart does, how to initialize it, or how the core execution works. These are minimum viable documentation.

### High Importance (Common Workflows)
- **DOC-004, DOC-005, DOC-006:** Production deployments need metrics for monitoring, graceful shutdown for container orchestration, and understanding why services are configured differently.

### Medium Importance (Regular Usage/Tuning)
- **DOC-007 through DOC-010:** Important for operational understanding and advanced configuration but not blocking initial usage.

### Deferred/WON'T DO
- **DOC-011 through DOC-014:** Either service-specific examples (belong in integration docs), advanced features (optional), or overly detailed implementation patterns (reference examples). These can be addressed in future loops after core README is complete.

---

## Implementation Notes

1. **Content reuse:** All proposed content above can be incorporated directly into README.md or docs/architecture.md
2. **Code examples:** Should include actual imports and method calls from Mozart codebase for accuracy
3. **Configuration defaults:** Reference actual default values from CircuitBreakerConfig and ServiceConfig dataclasses
4. **Testing:** After writing docs, verify all code examples compile and run against Mozart codebase

---

## Success Criteria

✅ All 10 PENDING gaps have draft content with clear locations in README structure  
✅ DOC-011 identified for maintainer clarification before implementation  
✅ DOC-012, DOC-013, DOC-014 deferred to advanced/integration documentation (future loop)  
✅ Fix order reflects critical → high → medium priority  
✅ Proposed content is concrete and ready for copy-paste into README  
