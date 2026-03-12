"""Gateway routes for SurfSense integration."""

from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.client import DeerFlowClient
from src.integrations.surfsense import SurfSenseClient, get_surfsense_config, resolve_surfsense_search_space_id
from src.models.routing import resolve_doc_edit_candidate_models

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/surfsense", tags=["surfsense"])


class SurfSenseSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    search_space_id: int | None = None
    project_key: str | None = None
    top_k: int = Field(default=8, ge=1, le=50)
    document_types: list[str] = Field(default_factory=list)


class SurfSenseExportRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content_markdown: str = Field(..., min_length=1)
    source_type: str = Field(default="artifact")
    source_run_id: str | None = None
    source_thread_id: str | None = None
    search_space_id: int | None = None
    project_key: str | None = None


class SurfSenseResearchRequest(BaseModel):
    question: str = Field(..., min_length=1)
    search_space_id: int | None = None
    project_key: str | None = None
    thread_id: str | None = None
    context_blocks: list[dict] = Field(default_factory=list)
    preferred_model: str | None = None


@router.get("/config")
async def get_surfsense_integration_config(project_key: str | None = None) -> dict:
    config = get_surfsense_config()
    return {
        "base_url": config.base_url,
        "sync_enabled": config.sync_enabled,
        "configured": bool(config.bearer_token),
        "default_search_space_id": config.default_search_space_id,
        "resolved_search_space_id": resolve_surfsense_search_space_id(project_key=project_key),
        "project_mapping_keys": sorted(config.project_mapping),
    }


@router.get("/search-spaces")
async def list_surfsense_search_spaces() -> list[dict]:
    try:
        return await SurfSenseClient().list_search_spaces()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SurfSense request failed: {exc}") from exc


@router.post("/search")
async def search_surfsense(req: SurfSenseSearchRequest) -> dict:
    search_space_id = resolve_surfsense_search_space_id(
        explicit_search_space_id=req.search_space_id,
        project_key=req.project_key,
    )
    try:
        return await SurfSenseClient().search_documents(
            query=req.query,
            search_space_id=search_space_id,
            top_k=req.top_k,
            document_types=req.document_types or None,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SurfSense request failed: {exc}") from exc


@router.post("/export-note")
async def export_note_to_surfsense(req: SurfSenseExportRequest) -> dict:
    search_space_id = resolve_surfsense_search_space_id(
        explicit_search_space_id=req.search_space_id,
        project_key=req.project_key,
    )
    if search_space_id is None:
        raise HTTPException(status_code=400, detail="No SurfSense search space is configured")

    metadata = {
        "NOTE": True,
        "source_system": "maestroflow",
        "source_run_id": req.source_run_id,
        "source_thread_id": req.source_thread_id,
        "source_type": req.source_type,
        "project_key": req.project_key,
    }
    title = req.title.strip()
    try:
        client = SurfSenseClient()
        notes = await client.list_notes(search_space_id, limit=100)
        existing = next(
            (
                item
                for item in notes.get("items", [])
                if (item.get("document_metadata") or {}).get("source_system") == "maestroflow"
                and (item.get("document_metadata") or {}).get("source_run_id") == req.source_run_id
                and (item.get("document_metadata") or {}).get("source_type") == req.source_type
            ),
            None,
        )
        if existing is None:
            payload = await client.create_note(
                search_space_id=search_space_id,
                title=title,
                source_markdown=req.content_markdown,
                document_metadata=metadata,
            )
            return {"status": "created", "search_space_id": search_space_id, "note_id": payload["id"]}

        await client.update_note(
            search_space_id=search_space_id,
            note_id=existing["id"],
            title=title,
            source_markdown=req.content_markdown,
            document_metadata=metadata,
        )
        return {"status": "updated", "search_space_id": search_space_id, "note_id": existing["id"]}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"SurfSense export failed: {exc}") from exc


@router.post("/research")
async def research_with_surfsense_context(req: SurfSenseResearchRequest) -> dict:
    search_space_id = resolve_surfsense_search_space_id(
        explicit_search_space_id=req.search_space_id,
        project_key=req.project_key,
    )
    context_lines: list[str] = []
    if search_space_id is not None:
        context_lines.append(f"SurfSense search space ID: {search_space_id}")
    for index, block in enumerate(req.context_blocks, start=1):
        context_lines.append(f"Context block {index}: {block}")
    context_blob = "\n".join(context_lines).strip() or "No SurfSense context was supplied."
    prompt = (
        "You are handling a SurfSense escalation inside MaestroFlow.\n"
        "Prioritize the SurfSense context first. Only rely on external web knowledge if the supplied internal context is insufficient.\n"
        "Return concise markdown with sections: Answer, Key Sources, Suggested Follow-up.\n\n"
        f"User question:\n{req.question}\n\n"
        f"SurfSense context:\n{context_blob}\n"
    )

    thread_id = req.thread_id or f"surfsense-{search_space_id or 'default'}-{uuid.uuid4().hex[:8]}"
    resolved_candidates = resolve_doc_edit_candidate_models(
        location="mixed",
        strength="fast",
        preferred_model=req.preferred_model,
    )
    resolved_model_name = resolved_candidates[0] if resolved_candidates else None
    try:
        response = DeerFlowClient(
            model_name=resolved_model_name,
            thinking_enabled=True,
            subagent_enabled=True,
        ).chat(prompt, thread_id=thread_id)
    except Exception as exc:
        logger.error("SurfSense escalation failed for thread %s", thread_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"MaestroFlow research failed: {exc}") from exc

    return {
        "thread_id": thread_id,
        "search_space_id": search_space_id,
        "final_answer": response,
        "provenance": {
            "source_system": "maestroflow",
            "thread_id": thread_id,
            "project_key": req.project_key,
            "search_space_id": search_space_id,
            "requested_model": req.preferred_model,
            "resolved_model": resolved_model_name,
        },
    }
