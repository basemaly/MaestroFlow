"""Zep long-term memory client for MaestroFlow.

Syncs conversation facts from MaestroFlow's memory system to Zep's knowledge
graph for structured entity/relationship storage and cross-session retrieval.

Zep provides a richer memory backend than the flat JSON file:
- Entity extraction and graph relationships
- Temporal fact tracking with confidence scores
- Cross-thread memory search

Requires ZEP_URL (e.g. http://localhost:8000) and optionally ZEP_API_KEY.
Fails silently if Zep is unreachable.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 10.0


def _get_config() -> dict[str, str]:
    return {
        "url": os.environ.get("ZEP_URL", "").rstrip("/"),
        "api_key": os.environ.get("ZEP_API_KEY", ""),
    }


def _is_configured() -> bool:
    return bool(_get_config()["url"])


def _headers() -> dict[str, str]:
    cfg = _get_config()
    h: dict[str, str] = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        h["Authorization"] = f"Api-Key {cfg['api_key']}"
    return h


def _base_url() -> str:
    return _get_config()["url"]


def ping() -> bool:
    """Return True if Zep is reachable."""
    if not _is_configured():
        return False
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{_base_url()}/healthz", headers=_headers())
            return resp.status_code < 500
    except Exception:
        return False


def ensure_user(user_id: str, *, metadata: dict[str, Any] | None = None) -> bool:
    """Create or update a Zep user. Returns True on success."""
    if not _is_configured():
        return False
    payload: dict[str, Any] = {"user_id": user_id}
    if metadata:
        payload["metadata"] = metadata
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            # Upsert: try create, ignore 409 conflict
            resp = client.post(f"{_base_url()}/users", json=payload, headers=_headers())
            if resp.status_code in (200, 201, 409):
                return True
            logger.debug("Zep ensure_user unexpected status %s", resp.status_code)
            return False
    except Exception as exc:
        logger.debug("Zep ensure_user failed: %s", exc)
        return False


def ensure_session(session_id: str, user_id: str, *, metadata: dict[str, Any] | None = None) -> bool:
    """Create or update a Zep session (maps to a MaestroFlow thread). Returns True on success."""
    if not _is_configured():
        return False
    payload: dict[str, Any] = {"session_id": session_id, "user_id": user_id}
    if metadata:
        payload["metadata"] = metadata
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(f"{_base_url()}/sessions", json=payload, headers=_headers())
            if resp.status_code in (200, 201, 409):
                return True
            # Try PATCH if POST fails with 4xx
            if resp.status_code == 400:
                patch = client.patch(f"{_base_url()}/sessions/{session_id}", json=payload, headers=_headers())
                return patch.status_code < 300
            logger.debug("Zep ensure_session unexpected status %s", resp.status_code)
            return False
    except Exception as exc:
        logger.debug("Zep ensure_session failed: %s", exc)
        return False


def add_messages(session_id: str, messages: list[dict[str, str]]) -> bool:
    """Append messages to a Zep session for fact extraction.

    Messages should be dicts with 'role' and 'content' keys.
    Returns True on success.
    """
    if not _is_configured() or not messages:
        return False
    zep_messages = [
        {
            "role": m.get("role", "user"),
            "role_type": "user" if m.get("role") == "user" else "assistant",
            "content": m.get("content", ""),
        }
        for m in messages
    ]
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(
                f"{_base_url()}/sessions/{session_id}/messages",
                json={"messages": zep_messages},
                headers=_headers(),
            )
            if resp.status_code < 300:
                return True
            logger.debug("Zep add_messages status %s: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.debug("Zep add_messages failed: %s", exc)
        return False


def search_memory(session_id: str, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search Zep's graph memory for relevant facts about a query.

    Returns a list of fact dicts: {fact, valid_at, invalid_at, confidence}
    Returns empty list if Zep is not configured or unreachable.
    """
    if not _is_configured():
        return []
    try:
        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(
                f"{_base_url()}/sessions/{session_id}/memory/search",
                json={"text": query, "limit": limit},
                headers=_headers(),
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            return results[:limit] if isinstance(results, list) else []
    except Exception as exc:
        logger.debug("Zep search_memory failed for session %s: %s", session_id, exc)
        return []
