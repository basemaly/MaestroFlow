"""Built-in tool for previewing Calibre Server books before ingest."""

from __future__ import annotations

from langchain.tools import tool

from src.integrations.calibre_server import CalibreServerClient


def _preview_line(book: dict) -> str:
    authors = ", ".join(book.get("authors") or []) or "Unknown"
    tags = ", ".join(book.get("tags") or []) or "None"
    collections = ", ".join(
        book.get("user_metadata", {})
        .get("#kobocollections", {})
        .get("#value#", [])
        or []
    ) or "None"
    reasons = ", ".join(book.get("_match_reasons") or []) or "filter match"
    score = book.get("_match_score")
    score_text = f"{float(score):.1f}" if isinstance(score, (int, float)) else "-"
    return (
        f"- calibre_id={book.get('application_id')} | title={book.get('title')} | authors={authors} | "
        f"tags={tags} | collections={collections} | score={score_text} | matched_on={reasons}"
    )


@tool("preview_calibre_books_for_search_space", parse_docstring=True)
async def preview_calibre_books_for_search_space(
    search_space_id: int,
    query: str | None = None,
    title: str | None = None,
    author: str | None = None,
    tag: str | None = None,
    kobo_collection: str | None = None,
    series: str | None = None,
    publisher: str | None = None,
    limit: int = 10,
) -> str:
    """Preview Calibre Server books that would be ingested into a specific SurfSense search space.

    Use this before ingest when the user wants to review or refine a book selection.
    For user-review flows, preview first and only call ingest after the user approves the exact ids or filters.
    Require an explicit `search_space_id`. This tool does not write anything.

    Args:
        search_space_id: Exact SurfSense search space the user intends to ingest into.
        query: Optional natural-language description of the books to find.
        title: Optional exact title filter.
        author: Optional exact author filter.
        tag: Optional exact Calibre tag filter.
        kobo_collection: Optional exact Kobo Collection filter.
        series: Optional exact series filter.
        publisher: Optional exact publisher filter.
        limit: Maximum number of preview books to return.
    """
    books = await CalibreServerClient().discover_books(
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
        return (
            f"No Calibre books matched for search space {search_space_id}. "
            f"Filters: query={query or '-'}, title={title or '-'}, author={author or '-'}, "
            f"tag={tag or '-'}, collection={kobo_collection or '-'}, series={series or '-'}, "
            f"publisher={publisher or '-'}."
        )

    lines = [
        f"Preview for search space {search_space_id}: {len(books)} Calibre book(s) matched.",
        "Use the returned calibre_id values to approve a precise ingest if needed.",
        "",
    ]
    lines.extend(_preview_line(book) for book in books)
    return "\n".join(lines)
