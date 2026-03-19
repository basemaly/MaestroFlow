"""Built-in tool for ingesting Calibre Server books into SurfSense search spaces."""

from __future__ import annotations

from typing import Any

from langchain.tools import tool
from markdownify import markdownify as html_to_markdown

from src.integrations.calibre_server import CalibreServerClient
from src.integrations.surfsense.client import SurfSenseClient


def _book_note_title(book: dict[str, Any]) -> str:
    return f"Calibre · {book.get('title', 'Untitled')} · #{book.get('application_id')}"


def _book_collections(book: dict[str, Any]) -> list[str]:
    return (
        book.get("user_metadata", {})
        .get("#kobocollections", {})
        .get("#value#", [])
        or []
    )


def _book_description_markdown(book: dict[str, Any]) -> str:
    comments = str(book.get("comments") or "").strip()
    if not comments:
        return ""
    return html_to_markdown(comments).strip()


def _book_toc_markdown(book: dict[str, Any]) -> str:
    contents = (
        book.get("user_metadata", {})
        .get("#contents", {})
        .get("#value#")
    )
    if not contents:
        return ""
    return html_to_markdown(str(contents)).strip()


def _book_source_markdown(book: dict[str, Any], *, tag: str | None, kobo_collection: str | None) -> str:
    authors = ", ".join(book.get("authors") or []) or "Unknown"
    tags_value = ", ".join(book.get("tags") or []) or "None"
    collections_value = ", ".join(_book_collections(book)) or "None"
    formats_value = ", ".join(book.get("formats") or []) or "Unknown"
    identifiers = book.get("identifiers") or {}
    identifiers_lines = "\n".join(f"- {key}: {value}" for key, value in identifiers.items())
    description = _book_description_markdown(book)
    toc_markdown = _book_toc_markdown(book)

    sections = [
        f"# {book.get('title', 'Untitled')}",
        "",
        f"- Authors: {authors}",
        f"- Calibre ID: {book.get('application_id')}",
        f"- Library: {book.get('_library_id')}",
        f"- Tags: {tags_value}",
        f"- Kobo Collections: {collections_value}",
        f"- Formats: {formats_value}",
        f"- Published: {book.get('pubdate') or 'Unknown'}",
        f"- Last Modified: {book.get('last_modified') or 'Unknown'}",
        f"- Detail URL: {book.get('_detail_url') or ''}",
    ]

    if tag:
        sections.append(f"- Ingested via tag filter: {tag}")
    if kobo_collection:
        sections.append(f"- Ingested via collection filter: {kobo_collection}")

    if identifiers_lines:
        sections.extend(["", "## Identifiers", identifiers_lines])
    if description:
        sections.extend(["", "## Description", description])
    if toc_markdown:
        sections.extend(["", "## Contents", toc_markdown])

    return "\n".join(section for section in sections if section is not None).strip() + "\n"


async def _find_existing_note_id(
    *,
    search_space_id: int,
    title: str,
) -> int | None:
    payload = await SurfSenseClient().list_notes(search_space_id, limit=500)
    items = payload.get("items", [])
    for item in items:
        if str(item.get("title", "")).strip() != title:
            continue
        note_id = item.get("id")
        if isinstance(note_id, int):
            return note_id
    return None


@tool("ingest_calibre_books_to_search_space", parse_docstring=True)
async def ingest_calibre_books_to_search_space(
    search_space_id: int,
    calibre_ids: list[int] | None = None,
    query: str | None = None,
    title: str | None = None,
    author: str | None = None,
    tag: str | None = None,
    kobo_collection: str | None = None,
    series: str | None = None,
    publisher: str | None = None,
    limit: int | None = None,
) -> str:
    """Ingest Calibre Server books into a specific SurfSense search space as working-knowledge notes.

    Use this when the user explicitly asks to ingest or import books from the Calibre server
    into a chosen SurfSense search space. For review-driven workflows, call the preview tool first
    and only ingest after the user approves the exact ids or filters. Require an explicit `search_space_id`.

    Args:
        search_space_id: Exact SurfSense search space to ingest into.
        calibre_ids: Optional explicit Calibre book ids approved from a preview step.
        query: Natural-language description of the books to ingest.
        title: Optional exact title filter.
        author: Optional exact author filter.
        tag: Optional exact Calibre tag to ingest from.
        kobo_collection: Optional exact Kobo Collection to ingest from.
        series: Optional exact series filter.
        publisher: Optional exact publisher filter.
        limit: Optional cap on the number of books to ingest.
    """
    books = await CalibreServerClient().discover_books(
        calibre_ids=calibre_ids,
        query=query,
        title=title,
        author=author,
        tag=tag,
        kobo_collection=kobo_collection,
        series=series,
        publisher=publisher,
        limit=limit,
    )
    if not books:
        filters = []
        if calibre_ids:
            filters.append(f"calibre_ids={','.join(str(book_id) for book_id in calibre_ids)}")
        if query:
            filters.append(f"query={query}")
        if title:
            filters.append(f"title={title}")
        if author:
            filters.append(f"author={author}")
        if tag:
            filters.append(f"tag={tag}")
        if kobo_collection:
            filters.append(f"collection={kobo_collection}")
        if series:
            filters.append(f"series={series}")
        if publisher:
            filters.append(f"publisher={publisher}")
        return "No Calibre books matched the requested filters: " + ", ".join(filters)

    created = 0
    updated = 0
    notes_client = SurfSenseClient()
    for book in books:
        title = _book_note_title(book)
        markdown = _book_source_markdown(book, tag=tag, kobo_collection=kobo_collection)
        document_metadata = {
            "source_system": "calibre_server",
            "source_type": "book",
            "calibre_id": book.get("application_id"),
            "library_id": book.get("_library_id"),
            "tags": book.get("tags") or [],
            "kobo_collections": _book_collections(book),
            "detail_url": book.get("_detail_url"),
            "formats": book.get("formats") or [],
        }
        existing_note_id = await _find_existing_note_id(search_space_id=search_space_id, title=title)
        if existing_note_id is None:
            await notes_client.create_note(
                search_space_id=search_space_id,
                title=title,
                source_markdown=markdown,
                document_metadata=document_metadata,
            )
            created += 1
        else:
            await notes_client.update_note(
                search_space_id=search_space_id,
                note_id=existing_note_id,
                title=title,
                source_markdown=markdown,
                document_metadata=document_metadata,
            )
            updated += 1

    return (
        f"Ingested {len(books)} Calibre book(s) into search space {search_space_id}. "
        f"Created: {created}. Updated: {updated}. "
        f"Filters: calibre_ids={','.join(str(book_id) for book_id in calibre_ids) if calibre_ids else '-'}, "
        f"query={query or '-'}, title={title or '-'}, author={author or '-'}, tag={tag or '-'}, "
        f"collection={kobo_collection or '-'}, series={series or '-'}, publisher={publisher or '-'}."
    )
