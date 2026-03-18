# Workflow Graph Optimization Plan

## Goal

Treat MaestroFlow workflow routing as a mutable DAG experiment surface inside Autoresearcher so the system can benchmark faster and cheaper execution variants without bypassing Executive approval.

## Plan

- [x] Read project context, architecture, and decisions
- [x] Inspect current Autoresearcher, Executive, model-routing, and workflow graph surfaces
- [x] Capture the implementation checklist in `tasks/todo.md`
- [x] Add a workflow-route WDL schema and deterministic execution sandbox
- [x] Add per-node telemetry, quality checks, and composite scoring for workflow experiments
- [x] Add mutator strategies for model swaps and dependency parallelization
- [x] Extend Autoresearcher storage and service logic to support `workflow_route` experiments
- [x] Expose workflow-route experiment endpoints through gateway and Executive
- [x] Extend the Autoresearcher UI to launch and inspect workflow-route experiments
- [x] Add targeted backend tests for workflow-route execution, mutation, scoring, and promotion gating
- [x] Run verification on the changed backend and frontend surfaces

## Review

- The implementation will reuse the existing Autoresearcher and Executive approval loop rather than introducing a second promotion system.
- Workflow optimization will stay manual-start and experiment-scoped, matching the project decision to keep Autoresearcher as a lab instead of an always-on optimizer.
- The first pass will use deterministic synthetic workflows and heuristic mutations so routing experiments are reproducible before any live-traffic bandit rollout.
