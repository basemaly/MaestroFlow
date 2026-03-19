from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from src.executive.storage import get_executive_db_path
from src.integrations.activepieces import execute_flow
from src.integrations.browser_runtime import create_browser_job
from src.integrations.openviking import attach_pack, hydrate_context_packs
from src.integrations.stateweave import create_state_snapshot


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ExecutiveBlueprint(BaseModel):
    blueprint_id: str
    title: str
    description: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class BlueprintRun(BaseModel):
    run_id: str
    blueprint_id: str
    status: str
    current_step_index: int = 0
    heartbeat_at: datetime = Field(default_factory=_utc_now)
    lease_expires_at: datetime = Field(default_factory=lambda: _utc_now() + timedelta(minutes=10))
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


@contextmanager
def _conn() -> sqlite3.Connection:
    db_path = get_executive_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_blueprints (
            blueprint_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            blueprint_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_blueprint_runs (
            run_id TEXT PRIMARY KEY,
            blueprint_id TEXT NOT NULL,
            status TEXT NOT NULL,
            current_step_index INTEGER NOT NULL,
            heartbeat_at TEXT NOT NULL,
            lease_expires_at TEXT NOT NULL,
            outputs_json TEXT NOT NULL,
            error TEXT,
            run_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def save_blueprint(blueprint: ExecutiveBlueprint) -> ExecutiveBlueprint:
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_blueprints
            (blueprint_id, title, description, blueprint_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                blueprint.blueprint_id,
                blueprint.title,
                blueprint.description,
                blueprint.model_dump_json(),
                blueprint.created_at.isoformat(),
                blueprint.updated_at.isoformat(),
            ),
        )
    return blueprint


def create_blueprint(title: str, description: str, steps: list[dict[str, Any]]) -> ExecutiveBlueprint:
    now = _utc_now()
    return save_blueprint(
        ExecutiveBlueprint(
            blueprint_id=str(uuid.uuid4()),
            title=title,
            description=description,
            steps=steps,
            created_at=now,
            updated_at=now,
        )
    )


def list_blueprints() -> list[ExecutiveBlueprint]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT blueprint_json FROM executive_blueprints ORDER BY updated_at DESC"
        ).fetchall()
    return [ExecutiveBlueprint.model_validate_json(row["blueprint_json"]) for row in rows]


def get_blueprint(blueprint_id: str) -> ExecutiveBlueprint | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT blueprint_json FROM executive_blueprints WHERE blueprint_id = ?",
            (blueprint_id,),
        ).fetchone()
    return ExecutiveBlueprint.model_validate_json(row["blueprint_json"]) if row else None


def _save_run(run: BlueprintRun) -> BlueprintRun:
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_blueprint_runs
            (run_id, blueprint_id, status, current_step_index, heartbeat_at, lease_expires_at, outputs_json, error, run_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.blueprint_id,
                run.status,
                run.current_step_index,
                run.heartbeat_at.isoformat(),
                run.lease_expires_at.isoformat(),
                json.dumps(run.outputs),
                run.error,
                run.model_dump_json(),
                run.created_at.isoformat(),
                run.updated_at.isoformat(),
            ),
        )
    return run


def get_blueprint_run(run_id: str) -> BlueprintRun | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT run_json FROM executive_blueprint_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    return BlueprintRun.model_validate_json(row["run_json"]) if row else None


def list_blueprint_runs(limit: int = 20) -> list[BlueprintRun]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT run_json FROM executive_blueprint_runs ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [BlueprintRun.model_validate_json(row["run_json"]) for row in rows]


def touch_blueprint_run(run_id: str) -> BlueprintRun:
    run = get_blueprint_run(run_id)
    if run is None:
        raise ValueError(f"Unknown blueprint run '{run_id}'.")
    now = _utc_now()
    run.heartbeat_at = now
    run.lease_expires_at = now + timedelta(minutes=10)
    run.updated_at = now
    return _save_run(run)


async def _execute_step(step: dict[str, Any], run: BlueprintRun) -> dict[str, Any]:
    kind = str(step.get("kind") or "").strip()
    payload = dict(step.get("payload") or {})
    if kind == "activepieces_flow":
        flow_id = str(payload.get("flow_id") or "")
        return await execute_flow(flow_id, payload.get("input", {}), source="blueprint")
    if kind == "browser_job":
        return {"job": await create_browser_job(payload)}
    if kind == "context_pack_hydrate":
        pack_ids = list(payload.get("pack_ids") or [])
        scope_key = str(payload.get("scope_key") or f"blueprint:{run.run_id}")
        items, warning = await hydrate_context_packs(pack_ids)
        for item in items:
            attach_pack(scope_key, item["pack_id"], item)
        return {"items": items, "scope_key": scope_key, "warning": warning}
    if kind == "state_snapshot":
        target_kind = str(payload.get("target_kind") or "blueprint_run")
        target_id = str(payload.get("target_id") or run.run_id)
        label = str(payload.get("label") or f"Run {run.run_id} step {run.current_step_index + 1}")
        snapshot_payload = dict(payload.get("snapshot_payload") or run.outputs)
        return {"snapshot": create_state_snapshot(target_kind, target_id, label, snapshot_payload, {"blueprint_id": run.blueprint_id})}
    raise ValueError(f"Unsupported blueprint step kind '{kind}'.")


async def start_blueprint_run(blueprint_id: str) -> BlueprintRun:
    blueprint = get_blueprint(blueprint_id)
    if blueprint is None:
        raise ValueError(f"Unknown blueprint '{blueprint_id}'.")
    now = _utc_now()
    run = BlueprintRun(
        run_id=str(uuid.uuid4()),
        blueprint_id=blueprint_id,
        status="running",
        created_at=now,
        updated_at=now,
        heartbeat_at=now,
        lease_expires_at=now + timedelta(minutes=10),
    )
    _save_run(run)
    try:
        for index, step in enumerate(blueprint.steps):
            run.current_step_index = index
            run = touch_blueprint_run(run.run_id)
            run.outputs[f"step_{index}"] = await _execute_step(step, run)
            run.updated_at = _utc_now()
            _save_run(run)
        run.status = "completed"
        run.updated_at = _utc_now()
        return _save_run(run)
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.updated_at = _utc_now()
        return _save_run(run)


async def resume_blueprint_run(run_id: str) -> BlueprintRun:
    run = get_blueprint_run(run_id)
    if run is None:
        raise ValueError(f"Unknown blueprint run '{run_id}'.")
    blueprint = get_blueprint(run.blueprint_id)
    if blueprint is None:
        raise ValueError(f"Unknown blueprint '{run.blueprint_id}'.")
    if run.status == "completed":
        return run
    run.status = "running"
    _save_run(run)
    try:
        for index in range(run.current_step_index, len(blueprint.steps)):
            run.current_step_index = index
            run = touch_blueprint_run(run.run_id)
            run.outputs[f"step_{index}"] = await _execute_step(blueprint.steps[index], run)
            _save_run(run)
        run.status = "completed"
        run.updated_at = _utc_now()
        return _save_run(run)
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.updated_at = _utc_now()
        return _save_run(run)
