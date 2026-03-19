# Autoresearch

Autoresearch is a manual optimization lab for prompts, UI components, and workflow routing. It is intentionally separate from the live Executive control plane — nothing starts automatically, and no change reaches production without explicit approval.

---

## Domains

| Domain | What gets optimized | Score axis |
|--------|---------------------|------------|
| `subagent_prompt` | System prompts for subagent roles (general-purpose, writing-refiner, etc.) | Correctness · Efficiency · Speed |
| `workflow_route` | DAG routing definitions — node order, retry logic, edge conditions | Fitness · Latency ratio · Cost ratio |
| `ui_design` | React/HTML components critiqued by VLM | Visual score (0–10) |

---

## Experiment Lifecycle

```
draft → running → evaluated ──────────────────→ rejected
                           └──→ awaiting_approval → promoted
                                                  └→ rolled_back
running/evaluated → stopped
```

- **draft** — Created but not yet executed (unused by current service; experiments start as `running`).
- **running** — Mutations are being generated and benchmarked.
- **evaluated** — All candidates have been scored, but none beat champion + 0.03.
- **awaiting_approval** — A candidate beat the champion threshold. Waiting for Executive approval.
- **promoted** — Winner applied to live prompt registry. Immutable final state.
- **rejected** — Experiment discarded. Reason stored in `last_error`.
- **stopped** — Manually halted.
- **rolled_back** — Champion was explicitly rolled back via `/prompts/rollback`.

---

## Database Schema

SQLite database at `.deer-flow/autoresearch.db` (override with `AUTORESEARCH_DB_PATH`).

### `autoresearch_champions`

Stores the current champion prompt for each role. One row per role.

| Column | Type | Notes |
|--------|------|-------|
| `role` | TEXT PK | e.g. `general-purpose`, `workflow-route:research_report` |
| `prompt_text` | TEXT | Current champion prompt or workflow definition |
| `version` | INTEGER | Monotonically increasing; starts at 1 |
| `source_candidate_id` | TEXT | ID of the candidate that was promoted (NULL for rollbacks) |
| `updated_at` | TEXT | ISO8601 UTC |
| `promoted_by` | TEXT | Actor ID (e.g. `executive`, `user`) |

### `autoresearch_experiments`

One row per experiment run.

| Column | Notes |
|--------|-------|
| `experiment_id` | UUID |
| `domain` | `subagent_prompt` / `workflow_route` / `ui_design` |
| `role` | Target role |
| `status` | See lifecycle above |
| `champion_version` | Version at experiment start |
| `promotion_status` | `none` / `awaiting_approval` / `approved` / `rejected` / `rolled_back` |
| `metadata_json` | Domain-specific metadata |

### `autoresearch_candidates`

One row per candidate variant within an experiment.

| Column | Notes |
|--------|-------|
| `candidate_id` | UUID |
| `source` | `champion` (baseline) / `mutation` / `manual` |
| `score_json` | `CandidateScore` as JSON — correctness, efficiency, speed, composite |
| `metadata_json` | Strategy, benchmark feedback, critique, telemetry |

---

## API Reference

Base path: `/api/autoresearch`

### Read endpoints

```bash
# Get available roles, champions, workflow templates
GET /api/autoresearch/registry

# List experiments (most recent first)
GET /api/autoresearch/experiments?limit=50

# Get a specific experiment with candidates and benchmarks
GET /api/autoresearch/experiments/{experiment_id}

# Get screenshot for a ui_design candidate
GET /api/autoresearch/experiments/{experiment_id}/candidates/{candidate_id}/screenshot
```

### Create experiments

```bash
# Start a prompt optimization experiment
POST /api/autoresearch/experiments/prompt
{
  "role": "general-purpose",
  "max_mutations": 3,
  "benchmark_limit": 5,
  "title": "Optional title",
  "notes": "Optional context"
}

# Start a UI design experiment
POST /api/autoresearch/experiments/ui-design
{
  "prompt": "Improve the visual hierarchy and CTA emphasis",
  "component_code": "<section>...</section>",
  "title": "Pricing card polish",
  "max_iterations": 3
}

# Start a workflow route experiment
POST /api/autoresearch/experiments/workflow-route
{
  "template_id": "research_report",
  "max_mutations": 3
}
```

### Score, approve, reject, stop

```bash
# Submit a manual score for a candidate
POST /api/autoresearch/experiments/{id}/candidates/{cid}/score
{ "correctness": 0.85, "efficiency": 0.9, "speed": 0.7 }

# Approve (via Executive router)
POST /api/executive/autoresearch/experiments/{id}/approve

# Reject
POST /api/executive/autoresearch/experiments/{id}/reject
{ "reason": "Did not improve output quality" }

# Stop
POST /api/executive/autoresearch/experiments/{id}/stop
{ "reason": "User cancelled" }

# Rollback a role to a previous prompt
POST /api/autoresearch/prompts/rollback
{ "role": "general-purpose", "prompt_text": "...", "actor_id": "executive" }
```

---

## Integration with Executive

Autoresearch registers itself as a component in `src/executive/registry.py`. Executive can:

- **Approve** — calls `approve_experiment()`, promotes winner to champion registry.
- **Reject** — calls `reject_experiment()`, marks experiment rejected.
- **Stop** — calls `stop_experiment()`, halts a running experiment.
- **Rollback** — calls `rollback_role_prompt()`, creates a new champion version from provided text.

Autoresearch never calls Executive directly. The separation keeps the lab and the control plane independent.

---

## Adding Benchmark Cases

Benchmark cases are defined in `src/autoresearch/benchmarks.py`. Each case is a `BenchmarkSpec` with:

- A `BenchmarkCase` (case_id, role, title, prompt, expected_focus, validation_hint)
- A `task` string passed to the model under test
- A `BenchmarkValidator` with rules for validating correctness

To add cases for a new role, append entries to `_SPECS["your-role"]` in `benchmarks.py`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTORESEARCH_DB_PATH` | `.deer-flow/autoresearch.db` | Path to SQLite database |
| `AUTORESEARCH_META_OPTIMIZER_ENABLED` | `false` | Enable LLM-based mutation generation |
| `AUTORESEARCH_META_MODEL` | (default model) | LLM to use for mutation generation |
