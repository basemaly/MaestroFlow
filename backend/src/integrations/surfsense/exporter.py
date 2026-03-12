"""Sync export helpers from MaestroFlow into SurfSense."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import httpx

from .config import SurfSenseConfig, get_surfsense_config


def _build_doc_edit_markdown(state: dict[str, Any], winner: dict[str, Any], final_path: str) -> str:
    updated_at = datetime.now(UTC).isoformat()
    return (
        "---\n"
        "source_system: maestroflow\n"
        f"source_run_id: {state['run_id']}\n"
        "source_type: doc_edit\n"
        f"source_thread_id: {state.get('thread_id', '')}\n"
        f"version_id: {winner['version_id']}\n"
        f"model: {winner['model_name']}\n"
        f"score: {winner['score']:.3f}\n"
        f"exported_at: {updated_at}\n"
        "---\n\n"
        f"# {state.get('title') or 'MaestroFlow Doc Edit'}\n\n"
        f"Selected skill: `{winner['skill_name']}`  \n"
        f"Selected model: `{winner['model_name']}`  \n"
        f"Run ID: `{state['run_id']}`  \n"
        f"Final path: `{final_path}`\n\n"
        "## Final Version\n\n"
        f"{winner['output'].rstrip()}\n"
    )


def _find_existing_note(
    *,
    client: httpx.Client,
    search_space_id: int,
    run_id: str,
) -> dict[str, Any] | None:
    response = client.get(f"/search-spaces/{search_space_id}/notes", params={"page_size": 100})
    response.raise_for_status()
    payload = response.json()
    for item in payload.get("items", []):
        metadata = item.get("document_metadata") or {}
        if metadata.get("source_system") == "maestroflow" and metadata.get("source_run_id") == run_id:
            return item
    return None


def export_doc_edit_winner_to_surfsense(
    *,
    state: dict[str, Any],
    winner: dict[str, Any],
    final_path: str,
    project_key: str | None = None,
    explicit_search_space_id: int | None = None,
    config: SurfSenseConfig | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any] | None:
    config = config or get_surfsense_config()
    if not config.sync_enabled:
        return None

    search_space_id = config.resolve_search_space_id(
        explicit_search_space_id=explicit_search_space_id,
        project_key=project_key,
    )
    if search_space_id is None or not config.bearer_token:
        return None

    title = f"MaestroFlow Doc Edit: {state.get('title') or state['run_id']}"
    content = _build_doc_edit_markdown(state, winner, final_path)
    metadata = {
        "NOTE": True,
        "source_system": "maestroflow",
        "source_run_id": state["run_id"],
        "source_thread_id": state.get("thread_id"),
        "source_type": "doc_edit",
        "source_version_id": winner["version_id"],
        "final_path": final_path,
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "project_key": project_key,
    }

    with httpx.Client(
        base_url=config.api_base_url,
        headers=config.auth_headers,
        timeout=config.timeout_seconds,
        transport=transport,
    ) as client:
        existing = _find_existing_note(client=client, search_space_id=search_space_id, run_id=state["run_id"])
        if existing is None:
            response = client.post(
                f"/search-spaces/{search_space_id}/notes",
                json={
                    "title": title,
                    "source_markdown": content,
                    "document_metadata": metadata,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return {"search_space_id": search_space_id, "note_id": payload["id"], "status": "created"}

        response = client.put(
            f"/search-spaces/{search_space_id}/notes/{existing['id']}",
            json={
                "title": title,
                "source_markdown": content,
                "document_metadata": metadata,
            },
        )
        response.raise_for_status()
        return {"search_space_id": search_space_id, "note_id": existing["id"], "status": "updated"}
