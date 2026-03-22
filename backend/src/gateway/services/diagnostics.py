from __future__ import annotations

import json
import os
import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.executive.registry import get_component_registry
from src.executive.status import collect_system_status, get_component_log_path
from src.executive.storage import list_approvals, list_audit_entries


REPO_ROOT = Path(__file__).parents[4]
LOG_ROOT = REPO_ROOT / "logs"
_REQUEST_MESSAGE_RE = re.compile(
    r"^request\.(?P<kind>complete|failed) method=(?P<method>[A-Z]+) path=(?P<path>\S+)"
    r"(?: status=(?P<status>\d+))? duration_ms=(?P<duration_ms>[\d.]+)$"
)
_CONSOLE_PREFIX_RE = re.compile(
    r"^(?P<timestamp>[^|]+)\s+\|\s+(?P<service>[^|]+)\s+\|\s+(?P<level>[^|]+)\s+\|\s+"
    r"(?P<logger>[^|]+)(?:\s+\|\s+request=(?P<request_id>[^|]+))?(?:\s+\|\s+trace=(?P<trace_id>[^|]+))?"
    r"\s+\|\s+(?P<message>.*)$"
)


def _iso_or_none(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def _coerce_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).isoformat()
    except ValueError:
        return value


def _tail_text_lines(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []
    lines: deque[str] = deque(maxlen=max(1, limit))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.rstrip("\n")
            if stripped:
                lines.append(stripped)
    return list(lines)


def _parse_log_line(line: str) -> dict[str, Any]:
    stripped = line.strip()
    if not stripped:
        return {"raw": line}
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
            payload["raw"] = line
            payload["timestamp"] = _coerce_timestamp(payload.get("timestamp"))
            return payload
        except json.JSONDecodeError:
            pass
    console_match = _CONSOLE_PREFIX_RE.match(stripped)
    if console_match:
        data = console_match.groupdict()
        return {
            "timestamp": data.get("timestamp"),
            "service": data.get("service"),
            "level": data.get("level"),
            "logger": data.get("logger"),
            "request_id": data.get("request_id"),
            "trace_id": data.get("trace_id"),
            "message": data.get("message"),
            "raw": line,
        }
    return {"raw": line, "message": stripped}


def _parse_request_entry(payload: dict[str, Any]) -> dict[str, Any] | None:
    message = str(payload.get("message") or "")
    match = _REQUEST_MESSAGE_RE.match(message)
    if not match:
        return None
    parts = match.groupdict()
    return {
        "timestamp": payload.get("timestamp"),
        "service": payload.get("service") or "gateway",
        "request_id": payload.get("request_id"),
        "trace_id": payload.get("trace_id"),
        "kind": parts["kind"],
        "method": parts["method"],
        "path": parts["path"],
        "status": int(parts["status"]) if parts.get("status") else None,
        "duration_ms": float(parts["duration_ms"]) if parts.get("duration_ms") else None,
        "message": message,
        "raw": payload.get("raw"),
    }


def _iter_recent_log_payloads(path: Path, limit: int = 4000) -> list[dict[str, Any]]:
    return [_parse_log_line(line) for line in _tail_text_lines(path, limit)]


def list_log_components() -> list[dict[str, Any]]:
    registry = get_component_registry()
    components: list[dict[str, Any]] = []
    for component in registry.values():
        path = get_component_log_path(component.component_id)
        if path is None:
            continue
        exists = path.exists()
        stat = path.stat() if exists else None
        components.append(
            {
                "component_id": component.component_id,
                "label": component.label,
                "path": str(path),
                "exists": exists,
                "size_bytes": stat.st_size if stat else 0,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat() if stat else None,
            }
        )
    return sorted(components, key=lambda item: item["label"].lower())


def get_component_logs(component_id: str, *, lines: int = 100, contains: str | None = None) -> dict[str, Any]:
    path = get_component_log_path(component_id)
    if path is None:
        raise ValueError(f"No log file mapped for component '{component_id}'.")
    window = max(10, min(lines, 400))
    raw_lines = _tail_text_lines(path, 4000)
    if contains:
        needle = contains.lower()
        raw_lines = [line for line in raw_lines if needle in line.lower()]
    selected = raw_lines[-window:]
    return {
        "component_id": component_id,
        "path": str(path),
        "exists": path.exists(),
        "lines": [_parse_log_line(line) for line in selected],
    }


def list_request_entries(
    *,
    limit: int = 100,
    path_contains: str | None = None,
    status: int | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for payload in reversed(_iter_recent_log_payloads(LOG_ROOT / "gateway.log")):
        entry = _parse_request_entry(payload)
        if entry is None:
            continue
        if path_contains and path_contains.lower() not in str(entry["path"]).lower():
            continue
        if status is not None and entry.get("status") != status:
            continue
        if request_id and entry.get("request_id") != request_id:
            continue
        if trace_id and entry.get("trace_id") != trace_id:
            continue
        entries.append(entry)
        if len(entries) >= max(1, min(limit, 200)):
            break
    return entries


def list_trace_entries(*, limit: int = 100, trace_id: str | None = None) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in list_request_entries(limit=1000, trace_id=trace_id):
        trace = entry.get("trace_id")
        if not trace:
            continue
        current = grouped.get(trace)
        if current is None:
            grouped[trace] = {
                "trace_id": trace,
                "last_seen_at": entry.get("timestamp"),
                "request_count": 1,
                "paths": [entry.get("path")],
                "latest_status": entry.get("status"),
                "latest_request_id": entry.get("request_id"),
            }
            continue
        current["request_count"] += 1
        current["last_seen_at"] = current.get("last_seen_at") or entry.get("timestamp")
        if entry.get("path") and entry["path"] not in current["paths"]:
            current["paths"].append(entry["path"])
        if current.get("latest_status") is None:
            current["latest_status"] = entry.get("status")
        if current.get("latest_request_id") is None:
            current["latest_request_id"] = entry.get("request_id")
    items = list(grouped.values())
    items.sort(key=lambda item: item.get("last_seen_at") or "", reverse=True)
    return items[: max(1, min(limit, 200))]


def list_event_entries(*, limit: int = 100, kind: str | None = None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if kind in (None, "audit"):
        for entry in list_audit_entries(limit=limit):
            entries.append(
                {
                    "event_kind": "audit",
                    "event_id": entry.audit_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "title": entry.result_summary or entry.action_id,
                    "summary": f"{entry.action_id} on {entry.component_id}",
                    "status": entry.status,
                    "component_id": entry.component_id,
                    "action_id": entry.action_id,
                    "details": entry.details,
                }
            )
    if kind in (None, "approval"):
        for approval in list_approvals(limit=limit):
            entries.append(
                {
                    "event_kind": "approval",
                    "event_id": approval.approval_id,
                    "timestamp": approval.created_at.isoformat(),
                    "title": approval.preview.summary,
                    "summary": f"{approval.action_id} on {approval.component_id}",
                    "status": approval.status,
                    "component_id": approval.component_id,
                    "action_id": approval.action_id,
                    "details": approval.input,
                }
            )
    entries.sort(key=lambda item: item["timestamp"], reverse=True)
    return entries[: max(1, min(limit, 200))]


def _count_log_levels(path: Path, limit: int = 4000, recent_minutes: int = 15) -> dict[str, int]:
    counts = {"warnings": 0, "errors": 0}
    cutoff = datetime.now(UTC).timestamp() - (recent_minutes * 60)
    for payload in _iter_recent_log_payloads(path, limit):
        timestamp = payload.get("timestamp")
        if isinstance(timestamp, str):
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if parsed.astimezone(UTC).timestamp() < cutoff:
                    continue
            except ValueError:
                pass
        level = str(payload.get("level") or "").upper()
        if level == "WARNING":
            counts["warnings"] += 1
        elif level in {"ERROR", "CRITICAL"}:
            counts["errors"] += 1
    return counts


def _latest_plan_review_stats() -> dict[str, Any]:
    entries = list_request_entries(limit=400, path_contains="/api/planning/first-turn-review")
    if not entries:
        return {
            "count": 0,
            "latest_duration_ms": None,
            "max_duration_ms": None,
        }
    durations = [entry["duration_ms"] for entry in entries if isinstance(entry.get("duration_ms"), float)]
    return {
        "count": len(entries),
        "latest_duration_ms": durations[0] if durations else None,
        "max_duration_ms": max(durations) if durations else None,
    }


async def get_diagnostics_overview() -> dict[str, Any]:
    status = await collect_system_status()
    log_components = list_log_components()
    recent_requests = list_request_entries(limit=50)
    recent_traces = list_trace_entries(limit=50)
    recent_events = list_event_entries(limit=50)
    gateway_levels = _count_log_levels(LOG_ROOT / "gateway.log")
    plan_review_stats = _latest_plan_review_stats()
    failing_components = [component for component in status.components if component.state not in {"healthy", "disabled"}]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime": {
            "frontend_mode": os.getenv("MAESTROFLOW_FRONTEND_RUNTIME_MODE", "app"),
        },
        "status": status.model_dump(mode="json"),
        "summary": {
            "warnings": len(failing_components),
            "log_components": len(log_components),
            "recent_requests": len(recent_requests),
            "recent_traces": len(recent_traces),
            "recent_events": len(recent_events),
        },
        "signals": {
            "gateway_warnings": gateway_levels["warnings"],
            "gateway_errors": gateway_levels["errors"],
            "plan_review": plan_review_stats,
        },
        "sections": {
            "logs": {
                "component_count": len(log_components),
                "items": log_components[:6],
            },
            "requests": {
                "items": recent_requests[:12],
            },
            "traces": {
                "items": recent_traces[:12],
            },
            "events": {
                "items": recent_events[:12],
            },
        },
    }
