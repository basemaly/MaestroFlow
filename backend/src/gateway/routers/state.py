from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.gateway.contracts import build_health_envelope
from src.integrations.stateweave import create_state_snapshot, diff_state_snapshots, export_state_snapshot, get_snapshot, get_stateweave_config, list_snapshots

router = APIRouter(prefix="/api/state", tags=["stateweave"])


class StateSnapshotRequest(BaseModel):
    scope: str | None = None
    reference_id: str | None = None
    state_type: str | None = None
    target_kind: str | None = None
    target_id: str | None = None
    label: str = Field(min_length=1)
    summary: str | None = None
    data: dict | None = None
    payload: dict | None = None
    metadata: dict = Field(default_factory=dict)


class StateDiffRequest(BaseModel):
    left_snapshot_id: str | None = None
    right_snapshot_id: str | None = None
    snapshot_id_a: str | None = None
    snapshot_id_b: str | None = None


class StateExportRequest(BaseModel):
    snapshot_id: str = Field(min_length=1)
    export_format: str = "json"


@router.get("/config")
async def state_config() -> dict:
    config = get_stateweave_config()
    return {
        "base_url": "",
        "enabled": config.enabled,
        "configured": config.is_configured,
        "available": True,
        "warning": None if config.enabled else "StateWeave is disabled.",
        "health": build_health_envelope(
            configured=config.is_configured,
            available=True,
            healthy=True,
            summary="StateWeave snapshot store ready.",
        ),
        "error": None,
    }


@router.post("/snapshots")
async def state_create_snapshot(req: StateSnapshotRequest) -> dict:
    snapshot = create_state_snapshot(
        target_kind=req.target_kind or req.scope or req.state_type,
        target_id=req.target_id or req.reference_id or req.scope,
        label=req.label,
        payload=req.payload or req.data or {},
        metadata={"summary": req.summary, **req.metadata},
    )
    return {"available": True, "warning": None, "error": None, "snapshot": _to_public_snapshot(snapshot)}


@router.get("/snapshots")
async def state_list_snapshots(scope: str | None = None, reference_id: str | None = None, state_type: str | None = None, limit: int = 20) -> dict:
    snapshots = list_snapshots(target_kind=scope or state_type, target_id=reference_id, limit=limit)
    return {"available": True, "warning": None, "error": None, "snapshots": [_to_public_snapshot(item) for item in snapshots]}


@router.get("/snapshots/{snapshot_id}")
async def state_get_snapshot(snapshot_id: str) -> dict:
    snapshot = get_snapshot(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Unknown snapshot '{snapshot_id}'.")
    return {"available": True, "warning": None, "error": None, "snapshot": _to_public_snapshot(snapshot)}


@router.post("/diff")
async def state_diff(req: StateDiffRequest) -> dict:
    try:
        left_snapshot_id = req.left_snapshot_id or req.snapshot_id_a or ""
        right_snapshot_id = req.right_snapshot_id or req.snapshot_id_b or ""
        payload = diff_state_snapshots(left_snapshot_id, right_snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "available": True,
        "warning": None,
        "error": None,
        "left_snapshot_id": left_snapshot_id,
        "right_snapshot_id": right_snapshot_id,
        "summary": f"{payload['summary']['change_count']} change(s) detected.",
        "changes": [
            {
                "path": change["path"],
                "change_type": "modified" if change["change"] == "updated" else change["change"],
                "before": change.get("before"),
                "after": change.get("after"),
                "summary": None,
            }
            for change in payload["changes"]
        ],
        "left_snapshot": _to_public_snapshot(payload["snapshot_a"]),
        "right_snapshot": _to_public_snapshot(payload["snapshot_b"]),
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=True,
            summary="Snapshot diff generated.",
            metrics={"change_count": payload["summary"]["change_count"]},
        ),
    }


@router.post("/export")
async def state_export(req: StateExportRequest) -> dict:
    try:
        snapshot = export_state_snapshot(req.snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "available": True,
        "warning": None,
        "error": None,
        "snapshot_id": req.snapshot_id,
        "export_format": req.export_format,
        "payload": snapshot,
    }


def _to_public_snapshot(snapshot: dict) -> dict:
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "scope": snapshot["target_kind"],
        "reference_id": snapshot["target_id"],
        "label": snapshot["label"],
        "summary": snapshot.get("metadata", {}).get("summary"),
        "state_type": snapshot["target_kind"],
        "data": snapshot["payload"],
        "metadata": snapshot.get("metadata", {}),
        "created_at": snapshot["created_at"],
    }
