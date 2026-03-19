from __future__ import annotations

import hashlib
import json
from typing import Any

from .storage import create_snapshot, get_snapshot, list_snapshots


def _diff_values(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    if type(a) is not type(b):
        return [{"path": path or "$", "before": a, "after": b, "change": "type_changed"}]
    if isinstance(a, dict):
        changes: list[dict[str, Any]] = []
        keys = sorted(set(a) | set(b))
        for key in keys:
            next_path = f"{path}.{key}" if path else key
            if key not in a:
                changes.append({"path": next_path, "before": None, "after": b[key], "change": "added"})
            elif key not in b:
                changes.append({"path": next_path, "before": a[key], "after": None, "change": "removed"})
            else:
                changes.extend(_diff_values(a[key], b[key], next_path))
        return changes
    if isinstance(a, list):
        if a == b:
            return []
        return [{"path": path or "$", "before": a, "after": b, "change": "list_changed"}]
    if a != b:
        return [{"path": path or "$", "before": a, "after": b, "change": "updated"}]
    return []


def create_state_snapshot(
    target_kind: str | None = None,
    target_id: str | None = None,
    label: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    *,
    state_type: str | None = None,
) -> dict[str, Any]:
    resolved_kind = (target_kind or state_type or "unknown").strip()
    resolved_target_id = (target_id or resolved_kind).strip()
    resolved_label = (label or f"{resolved_kind} snapshot").strip()
    return create_snapshot(resolved_kind, resolved_target_id, resolved_label, payload or {}, metadata)


def diff_snapshots(snapshot_id_a: str, snapshot_id_b: str) -> dict[str, Any]:
    snap_a = get_snapshot(snapshot_id_a)
    snap_b = get_snapshot(snapshot_id_b)
    if snap_a is None or snap_b is None:
        raise ValueError("Both snapshots must exist to compute a diff.")
    changes = _diff_values(snap_a["payload"], snap_b["payload"])
    diff_fingerprint = hashlib.sha1(
        json.dumps(
            {
                "snapshot_id_a": snapshot_id_a,
                "snapshot_id_b": snapshot_id_b,
                "changes": changes,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "diff_id": f"diff_{diff_fingerprint[:16]}",
        "snapshot_a": snap_a,
        "snapshot_b": snap_b,
        "changes": changes,
        "summary": {
            "change_count": len(changes),
            "target_kind": snap_a["target_kind"],
        },
    }


def export_snapshot(snapshot_id: str) -> dict[str, Any]:
    snapshot = get_snapshot(snapshot_id)
    if snapshot is None:
        raise ValueError(f"Snapshot '{snapshot_id}' not found.")
    return snapshot


def diff_state_snapshots(snapshot_id_a: str, snapshot_id_b: str) -> dict[str, Any]:
    return diff_snapshots(snapshot_id_a, snapshot_id_b)


def export_state_snapshot(snapshot_id: str) -> dict[str, Any]:
    return export_snapshot(snapshot_id)


__all__ = [
    "create_state_snapshot",
    "diff_snapshots",
    "diff_state_snapshots",
    "export_snapshot",
    "export_state_snapshot",
    "get_snapshot",
    "list_snapshots",
]
