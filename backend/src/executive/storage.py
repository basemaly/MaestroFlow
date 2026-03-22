from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from sqlite3 import Connection
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

# Metrics for monitoring
_pool_metrics = {
    "connections_created": 0,
    "connections_reused": 0,
    "queries_executed": 0,
    "query_times": [],  # List of (query_type, duration_ms)
}
_metrics_lock = threading.Lock()

# Import metrics for pool monitoring
try:
    from src.observability.metrics import (
        measure_connection_wait_time,
        measure_db_query_time,
        db_connections_active,
        db_connections_total,
        db_connections_reused,
    )

    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.warning("Prometheus metrics not available; continuing without metrics")


class _MetricsEnabledConnection:
    """Wrapper around sqlite3.Connection to track query latency metrics.

    Transparently wraps execute() and executemany() calls with timing measurement
    when metrics are enabled. For all other operations, delegates to the underlying
    connection.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, parameters: tuple | None = None):
        """Execute SQL with latency tracking if metrics enabled."""
        if not METRICS_ENABLED:
            return self._conn.execute(sql, parameters) if parameters else self._conn.execute(sql)

        with measure_db_query_time(query_type=self._get_query_type(sql)):
            return self._conn.execute(sql, parameters) if parameters else self._conn.execute(sql)

    def executemany(self, sql: str, seq):
        """Execute SQL multiple times with latency tracking if metrics enabled."""
        if not METRICS_ENABLED:
            return self._conn.executemany(sql, seq)

        with measure_db_query_time(query_type=self._get_query_type(sql)):
            return self._conn.executemany(sql, seq)

    @staticmethod
    def _get_query_type(sql: str) -> str:
        """Extract query type from SQL string."""
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("SELECT"):
            return "select"
        elif sql_upper.startswith("INSERT"):
            return "insert"
        elif sql_upper.startswith("UPDATE"):
            return "update"
        elif sql_upper.startswith("DELETE"):
            return "delete"
        elif sql_upper.startswith("CREATE"):
            return "create"
        else:
            return "other"

    def __getattr__(self, name: str):
        """Delegate all other attributes/methods to the underlying connection."""
        return getattr(self._conn, name)


# Connection pool configuration
MAX_POOL_SIZE = int(os.getenv("EXECUTOR_DB_MAX_POOL_SIZE", "20"))
POOL_IDLE_TIMEOUT_SECONDS = int(os.getenv("EXECUTOR_DB_POOL_IDLE_TIMEOUT", "300"))

# Connection pool implementation
_connection_pool = {}
_pool_lock = threading.Lock()
_pool_last_accessed = {}  # Track last access time per connection for idle timeout

from src.executive.models import (
    ExecutiveActionPreview,
    ExecutiveApprovalRequest,
    ExecutiveAuditEntry,
    ExecutiveBlueprint,
    ExecutiveBlueprintRun,
    ExecutiveHeartbeat,
)

REPO_ROOT = Path(__file__).parents[3]
DEFAULT_DB_PATH = REPO_ROOT / ".deer-flow" / "executive.db"


def get_executive_db_path() -> Path:
    override = os.getenv("EXECUTIVE_DB_PATH")
    return Path(override).expanduser().resolve() if override else DEFAULT_DB_PATH


@contextmanager
def _db_conn():
    """Get a database connection from the pool or create a new one."""
    db_path = get_executive_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    thread_id = threading.get_ident()
    conn_key = f"{db_path}_{thread_id}"

    with _pool_lock:
        # Clean up idle connections (older than POOL_IDLE_TIMEOUT_SECONDS)
        current_time = time.time()
        idle_keys = [key for key, last_access in _pool_last_accessed.items() if current_time - last_access > POOL_IDLE_TIMEOUT_SECONDS]
        for key in idle_keys:
            if key in _connection_pool:
                try:
                    _connection_pool[key].close()
                    logger.debug(f"Closed idle connection {key}")
                except Exception as e:
                    logger.warning(f"Error closing idle connection {key}: {e}")
                del _connection_pool[key]
                del _pool_last_accessed[key]

        # Enforce max pool size (close oldest idle connection if at limit)
        if conn_key not in _connection_pool and len(_connection_pool) >= MAX_POOL_SIZE:
            oldest_key = min(_pool_last_accessed.items(), key=lambda x: x[1])[0]
            try:
                _connection_pool[oldest_key].close()
                logger.debug(f"Evicted oldest idle connection {oldest_key} (pool at max size)")
            except Exception as e:
                logger.warning(f"Error evicting connection {oldest_key}: {e}")
            del _connection_pool[oldest_key]
            del _pool_last_accessed[oldest_key]

        if conn_key not in _connection_pool:
            # Create new connection with optimized settings
            conn = sqlite3.connect(
                str(db_path),
                timeout=10,
                check_same_thread=False,  # Allow use from different threads
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.row_factory = sqlite3.Row
            _connection_pool[conn_key] = conn
            with _metrics_lock:
                _pool_metrics["connections_created"] += 1
            logger.debug(f"Created new DB connection (pool size: {len(_connection_pool)}/{MAX_POOL_SIZE})")
        else:
            with _metrics_lock:
                _pool_metrics["connections_reused"] += 1

        conn = _connection_pool[conn_key]
        _pool_last_accessed[conn_key] = time.time()

        # Update metrics (only if metrics are available)
        if METRICS_ENABLED:
            try:
                db_connections_active.labels(pool_name="executive").set(len(_connection_pool))
            except Exception as e:
                logger.warning(f"Failed to update metrics: {e}")

    _ensure_schema(conn)

    # Wrap connection with metrics tracking
    wrapped_conn = _MetricsEnabledConnection(conn) if METRICS_ENABLED else conn

    try:
        yield wrapped_conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _close_all_connections() -> None:
    """Close all connections in the pool. Use for application shutdown."""
    with _pool_lock:
        num_connections = len(_connection_pool)
        for key, conn in _connection_pool.items():
            try:
                conn.close()
                logger.debug(f"Closed connection {key}")
            except Exception as e:
                logger.warning(f"Error closing connection {key}: {e}")
        _connection_pool.clear()
        _pool_last_accessed.clear()
        logger.info(f"Closed all {num_connections} database connections")


def get_pool_metrics() -> dict:
    """Get current pool metrics for monitoring/testing."""
    with _pool_lock:
        total_connections = (len(_connection_pool)) if _connection_pool else 0
        created = _pool_metrics["connections_created"]
        reused = _pool_metrics["connections_reused"]
        total_ops = created + reused
        reuse_ratio = reused / total_ops if total_ops > 0 else 0
        return {
            "pool_size": total_connections,
            "max_pool_size": MAX_POOL_SIZE,
            "connections_created": created,
            "connections_reused": reused,
            "reuse_ratio": reuse_ratio,
        }


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_approvals (
            approval_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            component_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            preview_json TEXT NOT NULL,
            input_json TEXT NOT NULL,
            status TEXT NOT NULL,
            expires_at TEXT
        )
        """
    )
    # Add indices for frequently queried columns
    conn.execute("CREATE INDEX IF NOT EXISTS idx_approvals_status ON executive_approvals(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_approvals_created_at ON executive_approvals(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_approvals_component_action ON executive_approvals(component_id, action_id)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_audit (
            audit_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            component_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            input_summary TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            required_confirmation INTEGER NOT NULL,
            status TEXT NOT NULL,
            result_summary TEXT NOT NULL,
            error TEXT,
            details_json TEXT NOT NULL
        )
        """
    )
    # Add indices for frequently queried columns
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON executive_audit(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_component_action ON executive_audit(component_id, action_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON executive_audit(actor_type, actor_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_status ON executive_audit(status)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_runtime_overrides (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # Add index for updated_at for time-based queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runtime_overrides_updated_at ON executive_runtime_overrides(updated_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_blueprints (
            blueprint_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            status TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    # Add indices for frequently queried columns
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blueprints_status ON executive_blueprints(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blueprints_updated_at ON executive_blueprints(updated_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_blueprint_runs (
            run_id TEXT PRIMARY KEY,
            blueprint_id TEXT NOT NULL,
            status TEXT NOT NULL,
            current_step_index INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            last_heartbeat_at TEXT,
            lease_expires_at TEXT,
            finished_at TEXT,
            result_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    # Add indices for frequently queried columns
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blueprint_runs_blueprint_id ON executive_blueprint_runs(blueprint_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blueprint_runs_status ON executive_blueprint_runs(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blueprint_runs_started_at ON executive_blueprint_runs(started_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS executive_heartbeats (
            heartbeat_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            lease_expires_at TEXT,
            payload_json TEXT NOT NULL
        )
        """
    )
    # Add indices for frequently queried columns
    conn.execute("CREATE INDEX IF NOT EXISTS idx_heartbeats_scope ON executive_heartbeats(scope_type, scope_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_heartbeats_timestamp ON executive_heartbeats(timestamp)")


def create_approval(
    *,
    requested_by: str,
    component_id: str,
    action_id: str,
    preview: ExecutiveActionPreview,
    input_payload: dict[str, Any],
    expires_in_hours: int = 24,
) -> ExecutiveApprovalRequest:
    approval = ExecutiveApprovalRequest(
        approval_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        requested_by=requested_by,
        component_id=component_id,
        action_id=action_id,
        preview=preview,
        input=input_payload,
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(hours=expires_in_hours),
    )
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_approvals
            (approval_id, created_at, requested_by, component_id, action_id, preview_json, input_json, status, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval.approval_id,
                approval.created_at.isoformat(),
                approval.requested_by,
                approval.component_id,
                approval.action_id,
                approval.preview.model_dump_json(),
                json.dumps(input_payload),
                approval.status,
                approval.expires_at.isoformat() if approval.expires_at else None,
            ),
        )
    return approval


def get_approval(approval_id: str) -> ExecutiveApprovalRequest | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT approval_id, created_at, requested_by, component_id, action_id, preview_json, input_json, status, expires_at
            FROM executive_approvals WHERE approval_id = ?
            """,
            (approval_id,),
        ).fetchone()
    if row is None:
        return None
    return ExecutiveApprovalRequest(
        approval_id=row[0],
        created_at=datetime.fromisoformat(row[1]),
        requested_by=row[2],
        component_id=row[3],
        action_id=row[4],
        preview=ExecutiveActionPreview.model_validate_json(row[5]),
        input=json.loads(row[6]),
        status=row[7],
        expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
    )


def list_approvals(limit: int = 50) -> list[ExecutiveApprovalRequest]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT approval_id, created_at, requested_by, component_id, action_id, preview_json, input_json, status, expires_at
            FROM executive_approvals
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        ExecutiveApprovalRequest(
            approval_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            requested_by=row[2],
            component_id=row[3],
            action_id=row[4],
            preview=ExecutiveActionPreview.model_validate_json(row[5]),
            input=json.loads(row[6]),
            status=row[7],
            expires_at=datetime.fromisoformat(row[8]) if row[8] else None,
        )
        for row in rows
    ]


def update_approval_status(approval_id: str, status: str) -> None:
    with _db_conn() as conn:
        conn.execute(
            "UPDATE executive_approvals SET status = ? WHERE approval_id = ?",
            (status, approval_id),
        )


def append_audit_entry(entry: ExecutiveAuditEntry) -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO executive_audit
            (audit_id, timestamp, actor_type, actor_id, component_id, action_id, input_summary, risk_level,
             required_confirmation, status, result_summary, error, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.audit_id,
                entry.timestamp.isoformat(),
                entry.actor_type,
                entry.actor_id,
                entry.component_id,
                entry.action_id,
                entry.input_summary,
                entry.risk_level,
                1 if entry.required_confirmation else 0,
                entry.status,
                entry.result_summary,
                entry.error,
                json.dumps(entry.details),
            ),
        )


def list_audit_entries(limit: int = 100) -> list[ExecutiveAuditEntry]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT audit_id, timestamp, actor_type, actor_id, component_id, action_id, input_summary, risk_level,
                   required_confirmation, status, result_summary, error, details_json
            FROM executive_audit
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        ExecutiveAuditEntry(
            audit_id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            actor_type=row[2],
            actor_id=row[3],
            component_id=row[4],
            action_id=row[5],
            input_summary=row[6],
            risk_level=row[7],
            required_confirmation=bool(row[8]),
            status=row[9],
            result_summary=row[10],
            error=row[11],
            details=json.loads(row[12]),
        )
        for row in rows
    ]


def set_runtime_override(key: str, value: dict[str, Any]) -> None:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_runtime_overrides (key, value_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, json.dumps(value), datetime.now(UTC).isoformat()),
        )


def get_runtime_override(key: str) -> dict[str, Any] | None:
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT value_json FROM executive_runtime_overrides WHERE key = ?",
            (key,),
        ).fetchone()
    return json.loads(row[0]) if row else None


def upsert_blueprint(blueprint: ExecutiveBlueprint) -> ExecutiveBlueprint:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_blueprints
            (blueprint_id, name, description, steps_json, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                blueprint.blueprint_id,
                blueprint.name,
                blueprint.description,
                json.dumps([step.model_dump(mode="json") for step in blueprint.steps]),
                blueprint.status,
                json.dumps(blueprint.metadata),
                blueprint.created_at.isoformat(),
                blueprint.updated_at.isoformat(),
            ),
        )
    return blueprint


def _row_to_blueprint(row: sqlite3.Row) -> ExecutiveBlueprint:
    steps_data = json.loads(row["steps_json"])
    # Ensure steps are in the correct format
    steps = []
    for step in steps_data:
        if isinstance(step, dict):
            steps.append(step)
        else:
            # Handle case where step might be a tuple or other format
            steps.append(dict(step) if hasattr(step, "_asdict") else dict(step))

    return ExecutiveBlueprint(
        blueprint_id=row["blueprint_id"],
        name=row["name"],
        description=row["description"],
        steps=steps,
        status=row["status"],
        metadata=json.loads(row["metadata_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def list_blueprints(limit: int = 50) -> list[ExecutiveBlueprint]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT blueprint_id, name, description, steps_json, status, metadata_json, created_at, updated_at
            FROM executive_blueprints
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_blueprint(row) for row in rows]


def get_blueprint(blueprint_id: str) -> ExecutiveBlueprint | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT blueprint_id, name, description, steps_json, status, metadata_json, created_at, updated_at
            FROM executive_blueprints
            WHERE blueprint_id = ?
            """,
            (blueprint_id,),
        ).fetchone()
    return _row_to_blueprint(row) if row else None


def upsert_blueprint_run(run: ExecutiveBlueprintRun) -> ExecutiveBlueprintRun:
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO executive_blueprint_runs
            (run_id, blueprint_id, status, current_step_index, started_at, last_heartbeat_at, lease_expires_at, finished_at, result_json, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.run_id,
                run.blueprint_id,
                run.status,
                run.current_step_index,
                run.started_at.isoformat(),
                run.last_heartbeat_at.isoformat() if run.last_heartbeat_at else None,
                run.lease_expires_at.isoformat() if run.lease_expires_at else None,
                run.finished_at.isoformat() if run.finished_at else None,
                json.dumps(run.result),
                json.dumps(run.metadata),
            ),
        )
    return run


def _row_to_blueprint_run(row: sqlite3.Row) -> ExecutiveBlueprintRun:
    return ExecutiveBlueprintRun(
        run_id=row["run_id"],
        blueprint_id=row["blueprint_id"],
        status=row["status"],
        current_step_index=row["current_step_index"],
        started_at=datetime.fromisoformat(row["started_at"]),
        last_heartbeat_at=datetime.fromisoformat(row["last_heartbeat_at"]) if row["last_heartbeat_at"] else None,
        lease_expires_at=datetime.fromisoformat(row["lease_expires_at"]) if row["lease_expires_at"] else None,
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        result=json.loads(row["result_json"]),
        metadata=json.loads(row["metadata_json"]),
    )


def list_blueprint_runs(blueprint_id: str, limit: int = 50) -> list[ExecutiveBlueprintRun]:
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT run_id, blueprint_id, status, current_step_index, started_at, last_heartbeat_at, lease_expires_at, finished_at, result_json, metadata_json
            FROM executive_blueprint_runs
            WHERE blueprint_id = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (blueprint_id, limit),
        ).fetchall()
    return [_row_to_blueprint_run(row) for row in rows]


def get_blueprint_run(run_id: str) -> ExecutiveBlueprintRun | None:
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT run_id, blueprint_id, status, current_step_index, started_at, last_heartbeat_at, lease_expires_at, finished_at, result_json, metadata_json
            FROM executive_blueprint_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    return _row_to_blueprint_run(row) if row else None


def record_blueprint_heartbeat(
    *,
    scope_type: str,
    scope_id: str,
    payload: dict[str, Any] | None = None,
    lease_seconds: int = 3600,
) -> ExecutiveHeartbeat:
    heartbeat = ExecutiveHeartbeat(
        heartbeat_id=str(uuid.uuid4()),
        scope_type=scope_type,
        scope_id=scope_id,
        lease_expires_at=datetime.now(UTC) + timedelta(seconds=lease_seconds),
        payload=payload or {},
    )
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO executive_heartbeats
            (heartbeat_id, scope_type, scope_id, timestamp, lease_expires_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                heartbeat.heartbeat_id,
                heartbeat.scope_type,
                heartbeat.scope_id,
                heartbeat.timestamp.isoformat(),
                heartbeat.lease_expires_at.isoformat() if heartbeat.lease_expires_at else None,
                json.dumps(heartbeat.payload),
            ),
        )
    return heartbeat


def list_heartbeats(limit: int = 50, *, scope_type: str | None = None, scope_id: str | None = None) -> list[ExecutiveHeartbeat]:
    clauses = []
    values: list[Any] = []
    if scope_type is not None:
        clauses.append("scope_type = ?")
        values.append(scope_type)
    if scope_id is not None:
        clauses.append("scope_id = ?")
        values.append(scope_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _db_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT heartbeat_id, scope_type, scope_id, timestamp, lease_expires_at, payload_json
            FROM executive_heartbeats
            {where}
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (*values, limit),
        ).fetchall()
    heartbeats: list[ExecutiveHeartbeat] = []
    for row in rows:
        heartbeats.append(
            ExecutiveHeartbeat(
                heartbeat_id=row["heartbeat_id"],
                scope_type=row["scope_type"],
                scope_id=row["scope_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                lease_expires_at=datetime.fromisoformat(row["lease_expires_at"]) if row["lease_expires_at"] else None,
                payload=json.loads(row["payload_json"]),
            )
        )
    return heartbeats
