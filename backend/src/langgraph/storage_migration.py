from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

DEFAULT_DEV_CHECKPOINTER_URL = (
    "postgresql://postgres:postgres@127.0.0.1:55434/maestroflow_langgraph_v2"
)
DEFAULT_DEV_REDIS_URL = "redis://127.0.0.1:6379/0"


@dataclass(slots=True)
class CatalogSummary:
    threads: int
    runs: int
    assistants: int
    assistant_versions: int
    crons: int
    thread_ids: set[str]


@dataclass(slots=True)
class CheckpointSummary:
    checkpoints: int
    thread_ids: set[str]
    top_threads: list[dict[str, Any]]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_ops_catalog_path() -> Path:
    return _repo_root() / "backend" / ".langgraph_api" / ".langgraph_ops.pckl"


def default_backup_dir() -> Path:
    return _repo_root() / "backend" / ".deer-flow" / "langgraph-migrations"


def resolve_checkpointer_url(explicit: str | None = None) -> str:
    return explicit or os.getenv("LANGGRAPH_CHECKPOINTER_URL") or DEFAULT_DEV_CHECKPOINTER_URL


def ensure_langgraph_unpickle_env(
    *,
    database_uri: str | None = None,
    redis_uri: str | None = None,
    runtime_edition: str = "inmem",
) -> None:
    os.environ.setdefault("DATABASE_URI", database_uri or DEFAULT_DEV_CHECKPOINTER_URL)
    os.environ.setdefault("REDIS_URI", redis_uri or DEFAULT_DEV_REDIS_URL)
    os.environ.setdefault("LANGGRAPH_RUNTIME_EDITION", runtime_edition)


def load_ops_catalog(
    ops_path: Path | str | None = None,
    *,
    database_uri: str | None = None,
    redis_uri: str | None = None,
    runtime_edition: str = "inmem",
) -> dict[str, Any]:
    ensure_langgraph_unpickle_env(
        database_uri=database_uri,
        redis_uri=redis_uri,
        runtime_edition=runtime_edition,
    )
    from langgraph.checkpoint.memory import PersistentDict

    resolved_path = Path(ops_path or default_ops_catalog_path())
    store = PersistentDict(dict, filename=str(resolved_path))
    store.load()
    return dict(store)


def summarize_catalog(catalog: Mapping[str, Any]) -> CatalogSummary:
    threads = list(catalog.get("threads", []))
    return CatalogSummary(
        threads=len(threads),
        runs=len(catalog.get("runs", [])),
        assistants=len(catalog.get("assistants", [])),
        assistant_versions=len(catalog.get("assistant_versions", [])),
        crons=len(catalog.get("crons", [])),
        thread_ids={str(thread.get("thread_id")) for thread in threads if thread.get("thread_id")},
    )


def summarize_checkpoints(checkpointer_url: str) -> CheckpointSummary:
    with psycopg.connect(checkpointer_url) as conn, conn.cursor() as cur:
        cur.execute("select count(*) from checkpoints")
        checkpoints = int(cur.fetchone()[0])
        cur.execute(
            """
            select thread_id::text, count(*)::int as checkpoint_count
            from checkpoints
            group by thread_id
            order by checkpoint_count desc, thread_id
            limit 20
            """
        )
        top_threads = [
            {"thread_id": thread_id, "checkpoint_count": checkpoint_count}
            for thread_id, checkpoint_count in cur.fetchall()
        ]
        cur.execute("select distinct thread_id::text from checkpoints")
        thread_ids = {row[0] for row in cur.fetchall()}
    return CheckpointSummary(
        checkpoints=checkpoints,
        thread_ids=thread_ids,
        top_threads=top_threads,
    )


def build_migration_report(
    catalog_summary: CatalogSummary,
    checkpoint_summary: CheckpointSummary,
) -> dict[str, Any]:
    overlap = catalog_summary.thread_ids & checkpoint_summary.thread_ids
    catalog_only = sorted(catalog_summary.thread_ids - checkpoint_summary.thread_ids)
    checkpoint_only = sorted(checkpoint_summary.thread_ids - catalog_summary.thread_ids)
    return {
        "runtime_mode": "split",
        "catalog_threads": catalog_summary.threads,
        "catalog_runs": catalog_summary.runs,
        "checkpoint_rows": checkpoint_summary.checkpoints,
        "checkpoint_threads": len(checkpoint_summary.thread_ids),
        "thread_id_overlap": len(overlap),
        "catalog_only_threads": len(catalog_only),
        "checkpoint_only_threads": len(checkpoint_only),
        "catalog_only_thread_ids_sample": catalog_only[:10],
        "checkpoint_only_thread_ids_sample": checkpoint_only[:10],
        "top_checkpoint_threads": checkpoint_summary.top_threads,
        "migration_blockers": [
            "Visible thread metadata is stored in .langgraph_api via langgraph-runtime-inmem.",
            "Checkpoint thread_ids do not currently line up with the visible API catalog thread_ids.",
            "A runtime-edition switch without import tooling risks creating a fresh empty thread catalog.",
        ],
        "recommended_cutover": [
            "Back up .langgraph_api before any runtime change.",
            "Stand up a scratch non-inmem LangGraph runtime with the target backend.",
            "Import or replay the visible thread catalog into the target runtime.",
            "Verify native /threads/{id}, /history, and /state against current MaestroFlow-visible threads.",
            "Only then remove the gateway compatibility shim.",
        ],
    }


def normalize_for_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): normalize_for_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [normalize_for_json(item) for item in value]
    if isinstance(value, set):
        return sorted(normalize_for_json(item) for item in value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if callable(value):
        return repr(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return normalize_for_json(value.model_dump())
    if hasattr(value, "__dict__"):
        return normalize_for_json(vars(value))
    return value


def write_catalog_backup(
    catalog: Mapping[str, Any],
    *,
    report: Mapping[str, Any],
    output_path: Path | str,
    source_path: Path | str,
) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().astimezone().isoformat(),
        "source_path": str(source_path),
        "report": normalize_for_json(report),
        "catalog": normalize_for_json(dict(catalog)),
    }
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return destination
