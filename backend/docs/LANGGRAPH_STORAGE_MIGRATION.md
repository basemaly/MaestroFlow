# LangGraph Storage Migration

## Current State

MaestroFlow is currently running a split LangGraph storage model:

- Visible thread metadata and the API catalog live in `backend/.langgraph_api/.langgraph_ops.pckl` via `langgraph-runtime-inmem`.
- Graph execution checkpoints live in Postgres through the custom checkpointer configured in [config.yaml](/Volumes/BA/DEV/MaestroFlow/config.yaml) and [async_provider.py](/Volumes/BA/DEV/MaestroFlow/backend/src/agents/checkpointer/async_provider.py).
- MaestroFlow repairs empty native `history` and `state` reads at the gateway boundary in [langgraph_compat.py](/Volumes/BA/DEV/MaestroFlow/backend/src/gateway/routers/langgraph_compat.py).

This is stable enough for local use once `.langgraph_api` is host-mounted, but it is not a true single-store deployment.

## Why Not Flip It In Place

The installed runtime is `langgraph-runtime-inmem`. A blind switch to a different runtime edition or a new `DATABASE_URI` risks booting a fresh empty API catalog while leaving the old visible threads stranded in `.langgraph_api`.

The missing piece is not another environment variable. It is a verified import path from the visible thread catalog into the target runtime backend.

## Safe Migration Sequence

1. Run an audit of the current split state.

```bash
cd /Volumes/BA/DEV/MaestroFlow
backend/.venv/bin/python backend/scripts/langgraph_storage_migration.py audit
```

2. Write a full JSON backup bundle before changing the runtime.

```bash
cd /Volumes/BA/DEV/MaestroFlow
backend/.venv/bin/python backend/scripts/langgraph_storage_migration.py backup
```

3. Stand up a scratch LangGraph instance using the target runtime backend instead of touching the live local stack first.

4. Import or replay the visible thread catalog from the backup bundle into the scratch runtime.

5. Verify all of the following against known threads:

- `GET /threads/{id}`
- `POST /threads/{id}/history`
- `GET /threads/{id}/state`
- recent thread listing in the MaestroFlow sidebar
- direct reload of older thread pages

6. Remove the MaestroFlow compatibility shim only after the native LangGraph endpoints are correct.

## Tooling Added

- [langgraph_storage_migration.py](/Volumes/BA/DEV/MaestroFlow/backend/scripts/langgraph_storage_migration.py)
- [storage_migration.py](/Volumes/BA/DEV/MaestroFlow/backend/src/langgraph/storage_migration.py)

The audit report covers:

- API catalog thread count
- checkpoint row count
- distinct thread ID overlap
- sample thread IDs that exist only in the catalog or only in checkpoints
- a recommended cutover checklist

## Practical Recommendation

Keep the current mounted `inmem` runtime until a scratch migration proves that the target backend preserves:

- thread visibility
- message reloads
- checkpoint continuity
- MaestroFlow page-load behavior

That is safer than treating runtime migration as a configuration toggle.
