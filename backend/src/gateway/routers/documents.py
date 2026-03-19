"""Gateway routes for persistent editable documents."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.documents.ai import transform_selection
from src.documents.storage import (
    create_document,
    create_quick_action,
    create_snapshot,
    delete_quick_action,
    get_document,
    get_snapshot,
    list_documents,
    list_quick_actions,
    list_snapshots,
    restore_snapshot,
    update_document,
    update_quick_action,
)
from src.observability import make_trace_id, observe_span, summarize_for_trace

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    doc_id: str
    title: str
    content_markdown: str
    editor_json: dict[str, Any] | None = None
    writing_memory: str = ""
    status: str
    source_run_id: str | None = None
    source_version_id: str | None = None
    source_thread_id: str | None = None
    source_filepath: str | None = None
    created_at: str
    updated_at: str


class DocumentsListResponse(BaseModel):
    documents: list[DocumentResponse]


class CreateDocumentRequest(BaseModel):
    content_markdown: str = Field(..., min_length=1)
    title: str | None = Field(default=None, max_length=120)
    editor_json: dict[str, Any] | None = None
    writing_memory: str = Field(default="", max_length=8000)
    status: str = Field(default="draft", max_length=32)
    source_run_id: str | None = Field(default=None, max_length=120)
    source_version_id: str | None = Field(default=None, max_length=160)
    source_thread_id: str | None = Field(default=None, max_length=120)
    source_filepath: str | None = Field(default=None, max_length=1024)


class UpdateDocumentRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    content_markdown: str | None = None
    editor_json: dict[str, Any] | None = None
    writing_memory: str | None = Field(default=None, max_length=8000)
    status: str | None = Field(default=None, max_length=32)
    source_run_id: str | None = Field(default=None, max_length=120)
    source_version_id: str | None = Field(default=None, max_length=160)
    source_thread_id: str | None = Field(default=None, max_length=120)
    source_filepath: str | None = Field(default=None, max_length=1024)


class TransformDocumentRequest(BaseModel):
    document_markdown: str = Field(..., min_length=1)
    selection_markdown: str = Field(..., min_length=1)
    operation: Literal["rewrite", "shorten", "expand", "improve-clarity", "executive-summary", "bullets", "custom"]
    instruction: str | None = Field(default=None, max_length=4000)
    writing_memory: str | None = Field(default=None, max_length=8000)
    model_location: Literal["local", "remote", "mixed"] = "mixed"
    model_strength: Literal["fast", "cheap", "strong"] = "fast"
    preferred_model: str | None = Field(default=None, max_length=120)


class TransformDocumentResponse(BaseModel):
    transformed_markdown: str
    model_name: str


class DocumentQuickActionResponse(BaseModel):
    action_id: str
    name: str
    instruction: str
    created_at: str
    updated_at: str


class DocumentQuickActionsListResponse(BaseModel):
    actions: list[DocumentQuickActionResponse]


class CreateQuickActionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    instruction: str = Field(..., min_length=1, max_length=4000)


class UpdateQuickActionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    instruction: str | None = Field(default=None, min_length=1, max_length=4000)


class DocumentSnapshotResponse(BaseModel):
    snapshot_id: str
    doc_id: str
    label: str
    note: str | None = None
    source: str
    title: str
    content_markdown: str
    editor_json: dict[str, Any] | None = None
    writing_memory: str = ""
    created_at: str


class DocumentSnapshotsListResponse(BaseModel):
    snapshots: list[DocumentSnapshotResponse]


class CreateSnapshotRequest(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)
    source: str = Field(default="manual", max_length=40)


@router.get("", response_model=DocumentsListResponse)
async def list_saved_documents(limit: int = 50) -> DocumentsListResponse:
    return DocumentsListResponse.model_validate(list_documents(limit=limit))


@router.post("", response_model=DocumentResponse)
async def create_saved_document(req: CreateDocumentRequest) -> DocumentResponse:
    trace_id = make_trace_id(seed=req.title or req.content_markdown[:64])
    with observe_span("documents.create", trace_id=trace_id, input=req.model_dump()) as observation:
        document = create_document(**req.model_dump())
        observation.update(output=summarize_for_trace(document))
        return DocumentResponse.model_validate(document)


@router.get("/quick-actions", response_model=DocumentQuickActionsListResponse)
async def list_document_quick_actions() -> DocumentQuickActionsListResponse:
    return DocumentQuickActionsListResponse(
        actions=[DocumentQuickActionResponse.model_validate(item) for item in list_quick_actions()]
    )


@router.post("/quick-actions", response_model=DocumentQuickActionResponse)
async def create_document_quick_action(req: CreateQuickActionRequest) -> DocumentQuickActionResponse:
    action = create_quick_action(name=req.name, instruction=req.instruction)
    return DocumentQuickActionResponse.model_validate(action)


@router.put("/quick-actions/{action_id}", response_model=DocumentQuickActionResponse)
async def update_document_quick_action(action_id: str, req: UpdateQuickActionRequest) -> DocumentQuickActionResponse:
    try:
        action = update_quick_action(action_id, req.model_dump(exclude_unset=True))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentQuickActionResponse.model_validate(action)


@router.delete("/quick-actions/{action_id}")
async def delete_document_quick_action(action_id: str) -> dict[str, bool]:
    try:
        delete_quick_action(action_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_saved_document(doc_id: str) -> DocumentResponse:
    try:
        return DocumentResponse.model_validate(get_document(doc_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_saved_document(doc_id: str, req: UpdateDocumentRequest) -> DocumentResponse:
    trace_id = make_trace_id(seed=doc_id)
    with observe_span("documents.update", trace_id=trace_id, input={"doc_id": doc_id, **req.model_dump(exclude_unset=True)}) as observation:
        try:
            document = update_document(doc_id, req.model_dump(exclude_unset=True))
        except FileNotFoundError as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        observation.update(output=summarize_for_trace(document))
        return DocumentResponse.model_validate(document)


@router.get("/{doc_id}/snapshots", response_model=DocumentSnapshotsListResponse)
async def list_document_snapshots(doc_id: str, limit: int = 100) -> DocumentSnapshotsListResponse:
    try:
        snapshots = list_snapshots(doc_id, limit=limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentSnapshotsListResponse(
        snapshots=[DocumentSnapshotResponse.model_validate(item) for item in snapshots]
    )


@router.post("/{doc_id}/snapshots", response_model=DocumentSnapshotResponse)
async def create_document_snapshot(doc_id: str, req: CreateSnapshotRequest) -> DocumentSnapshotResponse:
    try:
        snapshot = create_snapshot(doc_id, label=req.label, note=req.note, source=req.source)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentSnapshotResponse.model_validate(snapshot)


@router.get("/{doc_id}/snapshots/{snapshot_id}", response_model=DocumentSnapshotResponse)
async def get_document_snapshot(doc_id: str, snapshot_id: str) -> DocumentSnapshotResponse:
    try:
        snapshot = get_snapshot(doc_id, snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentSnapshotResponse.model_validate(snapshot)


@router.post("/{doc_id}/snapshots/{snapshot_id}/restore", response_model=DocumentResponse)
async def restore_document_snapshot(doc_id: str, snapshot_id: str) -> DocumentResponse:
    try:
        document = restore_snapshot(doc_id, snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DocumentResponse.model_validate(document)


@router.post("/{doc_id}/actions/transform", response_model=TransformDocumentResponse)
async def transform_document(doc_id: str, req: TransformDocumentRequest) -> TransformDocumentResponse:
    trace_id = make_trace_id(seed=f"{doc_id}:{req.operation}")
    with observe_span("documents.transform", trace_id=trace_id, input={"doc_id": doc_id, **req.model_dump(exclude={"document_markdown"})}) as observation:
        try:
            document = get_document(doc_id)
        except FileNotFoundError as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        try:
            result = await transform_selection(
                **req.model_dump(exclude={"writing_memory"}),
                writing_memory=req.writing_memory if req.writing_memory is not None else document.get("writing_memory", ""),
            )
        except ValueError as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=500, detail=f"Document transform failed: {exc}") from exc
        observation.update(output=summarize_for_trace(result))
        return TransformDocumentResponse.model_validate(result)
