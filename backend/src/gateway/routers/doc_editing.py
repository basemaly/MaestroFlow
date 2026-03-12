"""Gateway routes for parallel document editing runs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from langgraph.types import Command

from src.doc_editing.graph import get_doc_edit_graph, make_run_id
from src.doc_editing.run_tracker import convert_doc_edit_upload, ensure_run_dir, get_run, list_runs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/doc-edit", tags=["doc-editing"])


class DocEditRequest(BaseModel):
    """Start a parallel doc-edit run."""

    document: str = Field(..., min_length=1, description="Markdown document to edit")
    skills: list[str] = Field(default_factory=lambda: ["writing-refiner", "argument-critic"])
    model_preference: str = Field(default="fast", pattern="^(local|fast|strong)$")
    token_budget: int = Field(default=4000, ge=250)


class DocEditStartResponse(BaseModel):
    """Response for a completed doc-edit run."""

    run_id: str
    title: str | None = None
    run_dir: str
    status: str
    final_path: str | None
    selected_skill: str | None
    versions: list[dict]
    token_count: int
    review_payload: dict | None = None


class DocEditUploadResponse(BaseModel):
    filename: str
    document: str


def _to_response_payload(run_id: str, run_dir: str, result: dict) -> DocEditStartResponse:
    selected_version = result.get("selected_version")
    review_payload = result.get("review_payload")
    status = "completed" if result.get("final_path") else "awaiting_selection"
    return DocEditStartResponse(
        run_id=run_id,
        title=result.get("title"),
        run_dir=run_dir,
        status=status,
        final_path=result.get("final_path"),
        selected_skill=selected_version["skill_name"] if selected_version else None,
        versions=result.get("ranked_versions", result.get("versions", [])),
        token_count=result.get("tokens_used", 0),
        review_payload=review_payload,
    )


@router.post("", response_model=DocEditStartResponse)
async def start_doc_edit(req: DocEditRequest) -> DocEditStartResponse:
    run_id = make_run_id()
    run_dir = ensure_run_dir(run_id)
    initial_state = {
        "document": req.document,
        "skills": req.skills,
        "model_preference": req.model_preference,
        "token_budget": req.token_budget,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "versions": [],
    }
    config = {"configurable": {"thread_id": run_id}}
    graph = await get_doc_edit_graph()

    try:
        result = await graph.ainvoke(initial_state, config=config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Doc edit run %s failed", run_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Doc edit run failed: {exc}") from exc

    if "__interrupt__" in result:
        pending = get_run(run_id)
        result = {
            "title": pending.get("title"),
            "ranked_versions": pending.get("versions", []),
            "tokens_used": pending.get("tokens_used", 0),
            "review_payload": pending.get("review_payload"),
            "final_path": pending.get("final_path"),
            "selected_version": pending.get("selected_version"),
        }
    return _to_response_payload(run_id, str(run_dir), result)


@router.get("/runs")
async def list_doc_runs(limit: int = 25) -> dict:
    return list_runs(limit=limit)


@router.get("/{run_id}")
async def get_doc_run(run_id: str) -> dict:
    try:
        return get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Doc edit run '{run_id}' not found") from exc


@router.put("/{run_id}/select/{skill_name}", response_model=DocEditStartResponse)
async def select_doc_run_version(run_id: str, skill_name: str) -> DocEditStartResponse:
    config = {"configurable": {"thread_id": run_id}}
    graph = await get_doc_edit_graph()
    try:
        result = await graph.ainvoke(Command(resume=skill_name), config=config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Doc edit run '{run_id}' not found") from exc
    except Exception as exc:
        logger.error("Doc edit selection failed for run %s", run_id, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Doc edit selection failed: {exc}") from exc

    return _to_response_payload(run_id, str(ensure_run_dir(run_id)), result)


@router.post("/upload", response_model=DocEditUploadResponse)
async def upload_doc_edit_file(file: UploadFile = File(...)) -> DocEditUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    try:
        content = await file.read()
        document = await convert_doc_edit_upload(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Doc edit upload failed for %s", file.filename, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Doc edit upload failed: {exc}") from exc
    return DocEditUploadResponse(filename=file.filename, document=document)
