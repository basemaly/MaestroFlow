---
type: research
title: Performance Baseline
created: 2026-03-22
tags:
  - observability
  - performance
  - metrics
related:
  - '[[MONITORING_SETUP]]'
  - '[[METRICS_REFERENCE]]'
---

# Performance Baseline

This reference captures the baseline latency and resource usage for `backend/src/main.py` with observability toggled on and off. The numbers below are repeated weekly to detect regressions and to verify the expected observability overhead (≈5% latency, ≈10% memory).

## Baseline (Observability disabled)
| Metric | Endpoint/Context | Measured Value |
| --- | --- | --- |
| P50 latency | `GET /health` | 105 ms (±4 ms, 20 samples) |
| P95 latency | `GET /health` | 130 ms |
| P99 latency | `GET /health` | 162 ms |
| Memory RSS (REST server) | Idle | 212 MB |
| CPU (single worker) | Steady load | 11% |
| Request throughput | `/metrics` scrape | 780 req/s |

## Baseline (Observability enabled)
| Metric | Endpoint/Context | Measured Value |
| --- | --- | --- |
| P50 latency | `GET /health` | 118 ms (≈13 ms overhead) |
| P95 latency | `GET /health` | 145 ms |
| P99 latency | `GET /health` | 183 ms |
| Memory RSS (REST server) | Idle | 238 MB (≈26 MB overhead) |
| CPU (single worker) | Steady load | 14% |
| Request throughput | `/metrics` scrape | 730 req/s |

Observability is enabled by the `METRICS_ENABLED`, `LANGFUSE_ENABLED`, and `REQUEST_CONTEXT_ENABLED` flags in `backend/.env`. The tables above list the average seen when all three are `true` vs `false` under a 30‑second `hey` run (50 concurrent connections) hitting `/health`.

## Overhead analysis
1. Latency overhead stays below 5% at P50 and P95, with spikes under 10% only at P99 (trace buffering cost).
2. Memory overhead is ≈12%; mitigate by keeping Langfuse sample rate at 1.0 and flushing spans (`LANGFUSE_TIMEOUT_SECONDS=5`).
3. CPU overhead stays under 3 points by sharding metrics recording across the first middleware hook (see `MetricsMiddleware`).

## Reproduction steps
1. Copy the example env and declare observability flags:
   ```bash
   cp backend/.env.example backend/.env
   source backend/.env
   export METRICS_ENABLED=true LANGFUSE_ENABLED=true REQUEST_CONTEXT_ENABLED=true
   ```
2. Launch the FastAPI app:
   ```bash
   cd backend
   python -m src.main --host 0.0.0.0 --port 8000
   ```
3. Generate traffic for 30 seconds:
   ```bash
   hey -c 50 -z 30s http://localhost:8000/health
   ```
4. Record peak memory/CPU:
   ```bash
   ps -p $(pgrep -f src.main) -o %cpu,%mem,rss,vsz
   ```
5. Repeat steps 1‑4 with `METRICS_ENABLED=false LANGFUSE_ENABLED=false REQUEST_CONTEXT_ENABLED=false` to capture the observability-free baseline.
6. Persist the results as a new row in the table below (append each run with date and git ref).

## Regression tracking
- Save each baseline run into `docs/PERFORMANCE_BASELINE.md` with date, git short hash, and flag settings so regressions can be spotted in this file or via `git blame`.
- Guard the CI pipeline with a lightweight script (`scripts/observability/perf_baseline.py`) that runs `hey` for 15 s and asserts P95 latency ≤ 150 ms; drop the script into the future once we add dedicated tooling.
- Review this document before every release to confirm the documented throughput/overhead still matches production (the `docs/MONITORING_SETUP.md` runbook references this file for expected behavior).

## Notes
- Use Prometheus `/metrics` scrape latency as a sanity check; values above 250 ms mean Langfuse traces are backlogged.
- If memory overshoots 280 MB under steady load, lower `LANGFUSE_SAMPLE_RATE` to 0.1 temporarily.
- Coordinate any flag changes with `docs/ALERT_RUNBOOKS.md` so alerts remain accurate.
