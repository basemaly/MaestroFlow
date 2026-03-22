# Mozart

Mozart is a resilient Maestro-managed AI agent with built-in fault tolerance, distributed execution, and comprehensive monitoring.

## Core Concepts

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

## Getting Started

### Quick Start

Mozart provides a centralized **HTTPClientManager** for managing HTTP requests to external services with built-in circuit breaking, connection pooling, and health checks.

#### Managed Services
Mozart monitors and protects requests to:
- **SurfSense** — Web scraping/data extraction
- **LiteLLM** — LLM API routing (High-Cost protection)
- **Langfuse** — Observability logging
- **LangGraph** — Agent framework integration
- **OpenViking** — Custom data source
- **ActivePieces** — Workflow automation
- **BrowserRuntime** — Browser automation
- **StateWeave** — State management service

#### Usage
```python
from mozart.http_client_manager import HTTPClientManager, ServiceName

manager = HTTPClientManager()
# GET request with circuit breaker protection
response = manager.get(ServiceName.SURFSENSE, "https://api.surfsense.io/data")
```

Each service has pre-configured resilience settings optimized for its characteristics.

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

## Monitoring & Observability

### Metrics & Observability

Mozart collects comprehensive metrics on circuit breaker behavior and executor pool performance.

#### Circuit Breaker Metrics
- **Request counts:** total, successful, failed, rejected, timeout
- **Response times:** min, max, average (milliseconds)
- **State changes:** history with timestamps
- **Pool status:** connection count, health status

#### Executor Pool Metrics
- **Task status breakdown:** pending, running, completed, failed
- **Queue metrics:** wait times from submission to execution
- **Execution times:** per-task duration distribution
- **Resource usage:** CPU percentage, memory percentage

Metrics are maintained in a sliding window (default: last 100 events) for performance.

#### Accessing Metrics
```python
circuit_breaker = manager.get_circuit_breaker(ServiceName.SURFSENSE)
metrics = circuit_breaker.metrics

print(f"Success rate: {metrics.successful}/{metrics.total}")
print(f"Avg response time: {metrics.average_response_time}ms")
```

## Configuration

### Service Configuration Tiers

Mozart pre-configures each service based on its cost and criticality:

#### High-Cost Services
- **LiteLLM** — Expensive LLM API calls
- Timeout: 60s, Max Retries: 2, Failure Threshold: 3
- Prevents retrying expensive failed requests too many times

#### Critical Services
- **SurfSense** — Core data extraction
- Timeout: 30s, Max Retries: 3, Failure Threshold: 5
- Tolerates more transient failures due to external factors

#### Non-Blocking Services
- **Langfuse** — Logging (failures don't block main workflow)
- Timeout: 5s, Max Retries: 1, Failure Threshold: 10
- Fast failure to prevent delays from non-critical services

#### Standard Services
- Default timeouts and retry counts for other services

Configuration is automatically applied through HTTPClientManager.

## Deployment & Production

### Graceful Shutdown

Mozart handles shutdown gracefully through signal handlers and cleanup hooks:

- **SIGTERM/SIGINT:** Initiates graceful shutdown, allows in-flight tasks to complete
- **Task completion timeout:** Default 30 seconds to finish pending tasks
- **Force termination:** After timeout, remaining tasks are cancelled
- **Resource cleanup:** Connections and executor pools closed properly

This is essential for Kubernetes and Docker deployments to prevent request loss.

## Advanced Topics
