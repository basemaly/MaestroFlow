"""Gateway routes for persistent editable documents."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.documents.ai import transform_selection
from src.documents.storage import create_document, get_document, list_documents, update_document
from src.observability import make_trace_id, observe_span, summarize_for_trace

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    doc_id: str
    title: str
    content_markdown: str
    editor_json: dict[str, Any] | None = None
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
    status: str = Field(default="draft", max_length=32)
    source_run_id: str | None = Field(default=None, max_length=120)
    source_version_id: str | None = Field(default=None, max_length=160)
    source_thread_id: str | None = Field(default=None, max_length=120)
    source_filepath: str | None = Field(default=None, max_length=1024)


class UpdateDocumentRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    content_markdown: str | None = None
    editor_json: dict[str, Any] | None = None
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
    model_location: Literal["local", "remote", "mixed"] = "mixed"
    model_strength: Literal["fast", "cheap", "strong"] = "fast"
    preferred_model: str | None = Field(default=None, max_length=120)


class TransformDocumentResponse(BaseModel):
    transformed_markdown: str
    model_name: str


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


@router.post("/{doc_id}/actions/transform", response_model=TransformDocumentResponse)
async def transform_document(doc_id: str, req: TransformDocumentRequest) -> TransformDocumentResponse:
    trace_id = make_trace_id(seed=f"{doc_id}:{req.operation}")
    with observe_span("documents.transform", trace_id=trace_id, input={"doc_id": doc_id, **req.model_dump(exclude={"document_markdown"})}) as observation:
        try:
            get_document(doc_id)
        except FileNotFoundError as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        try:
            result = await transform_selection(**req.model_dump())
        except ValueError as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            observation.update(output={"error": str(exc)})
            raise HTTPException(status_code=500, detail=f"Document transform failed: {exc}") from exc
        observation.update(output=summarize_for_trace(result))
        return TransformDocumentResponse.model_validate(result)
