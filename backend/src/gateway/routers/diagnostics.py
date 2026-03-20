from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.gateway.contracts import build_health_envelope
from src.gateway.services.diagnostics import (
    get_component_logs,
    get_diagnostics_overview,
    list_event_entries,
    list_log_components,
    list_request_entries,
    list_trace_entries,
)


router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/overview")
async def diagnostics_overview() -> dict:
    payload = await get_diagnostics_overview()
    return {
        **payload,
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=True,
            summary="Diagnostics overview collected.",
            details={"warning_count": payload["summary"]["warnings"]},
            metrics=payload["summary"],
        ),
        "error": None,
    }


@router.get("/logs/components")
async def diagnostics_log_components() -> dict:
    components = list_log_components()
    return {
        "components": components,
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=True,
            summary="Log components listed.",
            details={"component_count": len(components)},
            metrics={"component_count": len(components)},
        ),
        "error": None,
    }


@router.get("/logs/{component_id}")
async def diagnostics_component_logs(
    component_id: str,
    lines: int = Query(default=100, ge=10, le=400),
    contains: str | None = None,
) -> dict:
    try:
        payload = get_component_logs(component_id, lines=lines, contains=contains)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **payload,
        "health": build_health_envelope(
            configured=True,
            available=payload["exists"],
            healthy=payload["exists"],
            summary="Component logs loaded." if payload["exists"] else "No log file available for this component.",
            details={"line_count": len(payload["lines"])},
            metrics={"line_count": len(payload["lines"])},
        ),
        "error": None,
    }


@router.get("/requests")
async def diagnostics_requests(
    limit: int = Query(default=100, ge=1, le=200),
    path_contains: str | None = None,
    status: int | None = Query(default=None, ge=100, le=599),
    request_id: str | None = None,
    trace_id: str | None = None,
) -> dict:
    items = list_request_entries(
        limit=limit,
        path_contains=path_contains,
        status=status,
        request_id=request_id,
        trace_id=trace_id,
    )
    return {
        "items": items,
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=True,
            summary="Request diagnostics loaded.",
            details={"item_count": len(items)},
            metrics={"item_count": len(items)},
        ),
        "error": None,
    }


@router.get("/traces")
async def diagnostics_traces(
    limit: int = Query(default=100, ge=1, le=200),
    trace_id: str | None = None,
) -> dict:
    items = list_trace_entries(limit=limit, trace_id=trace_id)
    return {
        "items": items,
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=True,
            summary="Trace diagnostics loaded.",
            details={"item_count": len(items)},
            metrics={"item_count": len(items)},
        ),
        "error": None,
    }


@router.get("/events")
async def diagnostics_events(
    limit: int = Query(default=100, ge=1, le=200),
    kind: str | None = Query(default=None, pattern="^(audit|approval)?$"),
) -> dict:
    items = list_event_entries(limit=limit, kind=kind)
    return {
        "items": items,
        "health": build_health_envelope(
            configured=True,
            available=True,
            healthy=True,
            summary="Diagnostics events loaded.",
            details={"item_count": len(items)},
            metrics={"item_count": len(items)},
        ),
        "error": None,
    }
