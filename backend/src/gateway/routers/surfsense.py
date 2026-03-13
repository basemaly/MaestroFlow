"""Gateway routes for SurfSense integration."""

from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.integrations.surfsense import SurfSenseClient, get_surfsense_config, resolve_surfsense_search_space_id
from src.models.routing import resolve_doc_edit_candidate_models
from src.observability import make_trace_id, observe_span, summarize_for_trace

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/surfsense", tags=["surfsense"])
DEFAULT_LANGGRAPH_URL = "http://127.0.0.1:2024"


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


def _extract_response_text(result: dict | list) -> str:
    if isinstance(result, list):
        messages = result
    elif isinstance(result, dict):
        messages = result.get("messages", [])
    else:
        return ""

    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("type") == "human":
            break
        if msg.get("type") == "ai":
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                return content
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                text = "".join(parts).strip()
                if text:
                    return text
    return ""


async def _resolve_live_surfsense_scope(
    *,
    search_space_id: int | None,
    project_key: str | None,
) -> tuple[int | None, str | None, list[dict[str, str]]]:
    if search_space_id is None:
        return None, project_key, []

    try:
        search_spaces = await SurfSenseClient().list_search_spaces()
    except httpx.HTTPError as exc:
        return None, None, [
            {
                "type": "surfsense_access_notice",
                "summary": (
                    "Live SurfSense retrieval is unavailable from MaestroFlow for this run. "
                    "Use only the provided SurfSense context blocks."
                ),
                "error": str(exc),
            }
        ]

    accessible_ids = {int(item["id"]) for item in search_spaces if item.get("id") is not None}
    if search_space_id in accessible_ids:
        return search_space_id, project_key, []

    return None, None, [
        {
            "type": "surfsense_access_notice",
            "summary": (
                f"MaestroFlow's SurfSense integration token cannot access search space {search_space_id}. "
                "Use only the provided SurfSense context blocks and do not rely on live SurfSense tool calls."
            ),
        }
    ]


async def _create_or_resolve_langgraph_thread(thread_id: str | None) -> str:
    from langgraph_sdk import get_client

    if thread_id:
        try:
            uuid.UUID(thread_id)
            return thread_id
        except ValueError:
            logger.warning("Ignoring non-UUID thread_id for SurfSense escalation: %s", thread_id)

    client = get_client(url=DEFAULT_LANGGRAPH_URL)
    thread = await client.threads.create()
    return thread["thread_id"]


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
    with observe_span(
        "surfsense.search",
        trace_id=make_trace_id(seed=f"surfsense-search:{req.query}:{search_space_id or req.project_key or ''}"),
        input=req.model_dump(),
    ) as observation:
        try:
            result = await SurfSenseClient().search_documents(
                query=req.query,
                search_space_id=search_space_id,
                top_k=req.top_k,
                document_types=req.document_types or None,
            )
            observation.update(output=summarize_for_trace(result))
            return result
        except httpx.HTTPError as exc:
            observation.update(output={"error": str(exc)})
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
    with observe_span(
        "surfsense.export_note",
        trace_id=make_trace_id(seed=req.source_run_id or title),
        input=req.model_dump(exclude={"content_markdown"}),
        metadata={"search_space_id": search_space_id, "source_type": req.source_type},
    ) as observation:
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
                result = {"status": "created", "search_space_id": search_space_id, "note_id": payload["id"]}
                observation.update(output=result)
                return result

            await client.update_note(
                search_space_id=search_space_id,
                note_id=existing["id"],
                title=title,
                source_markdown=req.content_markdown,
                document_metadata=metadata,
            )
            result = {"status": "updated", "search_space_id": search_space_id, "note_id": existing["id"]}
            observation.update(output=result)
            return result
        except httpx.HTTPError as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=502, detail=f"SurfSense export failed: {exc}") from exc


@router.post("/research")
async def research_with_surfsense_context(req: SurfSenseResearchRequest) -> dict:
    requested_search_space_id = resolve_surfsense_search_space_id(
        explicit_search_space_id=req.search_space_id,
        project_key=req.project_key,
    )
    live_search_space_id, live_project_key, access_notes = await _resolve_live_surfsense_scope(
        search_space_id=requested_search_space_id,
        project_key=req.project_key,
    )
    context_blocks = [*req.context_blocks, *access_notes]
    context_lines: list[str] = []
    if requested_search_space_id is not None:
        context_lines.append(f"Requested SurfSense search space ID: {requested_search_space_id}")
    if live_search_space_id is not None:
        context_lines.append(f"Live SurfSense search space ID available to MaestroFlow: {live_search_space_id}")
    for index, block in enumerate(context_blocks, start=1):
        context_lines.append(f"Context block {index}: {block}")
    context_blob = "\n".join(context_lines).strip() or "No SurfSense context was supplied."
    prompt = (
        "You are handling a SurfSense escalation inside MaestroFlow.\n"
        "Prioritize the SurfSense context first. Only rely on external web knowledge if the supplied internal context is insufficient.\n"
        "Return concise markdown with sections: Answer, Key Sources, Suggested Follow-up.\n\n"
        f"User question:\n{req.question}\n\n"
        f"SurfSense context:\n{context_blob}\n"
    )

    thread_id = await _create_or_resolve_langgraph_thread(req.thread_id)
    trace_id = make_trace_id(seed=thread_id)
    resolved_candidates = resolve_doc_edit_candidate_models(
        location="mixed",
        strength="fast",
        preferred_model=req.preferred_model,
    )
    resolved_model_name = resolved_candidates[0] if resolved_candidates else None
    with observe_span(
        "surfsense.research",
        trace_id=trace_id,
        input=req.model_dump(),
        metadata={"thread_id": thread_id, "resolved_model_name": resolved_model_name},
    ) as observation:
        try:
            from langgraph_sdk import get_client

            client = get_client(url=DEFAULT_LANGGRAPH_URL)
            response = await client.runs.wait(
                thread_id,
                "lead_agent",
                input={"messages": [{"role": "human", "content": prompt}]},
                config={
                    "recursion_limit": 100,
                    "metadata": {
                        "trace_id": trace_id,
                        "source": "surfsense.research",
                    },
                },
                context={
                    "thread_id": thread_id,
                    "model_name": resolved_model_name,
                    "thinking_enabled": True,
                    "subagent_enabled": True,
                    "is_plan_mode": False,
                },
            )
        except Exception as exc:
            logger.error("SurfSense escalation failed for thread %s", thread_id, exc_info=True)
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=500, detail=f"MaestroFlow research failed: {exc}") from exc

        final_answer = _extract_response_text(response)
        if not final_answer:
            final_answer = (
                "Research launched in MaestroFlow. Open the linked thread to review the live result and continue the investigation."
            )

        result = {
            "thread_id": thread_id,
            "search_space_id": requested_search_space_id,
            "final_answer": final_answer,
            "provenance": {
                "source_system": "maestroflow",
                "thread_id": thread_id,
                "project_key": live_project_key,
                "requested_project_key": req.project_key,
                "search_space_id": requested_search_space_id,
                "live_search_space_id": live_search_space_id,
                "requested_model": req.preferred_model,
                "resolved_model": resolved_model_name,
            },
        }
        observation.update(output=summarize_for_trace(result))
        return result
