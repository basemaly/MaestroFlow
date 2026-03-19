from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .client import PinboardClient


def normalize_bookmark(raw: dict[str, Any]) -> dict[str, Any]:
    tags_raw = raw.get("tags") or raw.get("tag") or ""
    if isinstance(tags_raw, str):
        tags = [part.strip() for part in tags_raw.split() if part.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(part).strip() for part in tags_raw if str(part).strip()]
    else:
        tags = []

    title = str(raw.get("description") or raw.get("title") or "").strip()
    description = str(raw.get("extended") or raw.get("summary") or "").strip()
    href = str(raw.get("href") or raw.get("url") or "").strip()
    shared = str(raw.get("shared") or "").strip().lower() in {"yes", "true", "1"}
    toread = str(raw.get("toread") or "").strip().lower() in {"yes", "true", "1"}

    return {
        "url": href,
        "title": title or href or "Untitled bookmark",
        "description": description,
        "tags": tags,
        "created_at": raw.get("time"),
        "shared": shared,
        "toread": toread,
        "extended": description or None,
    }


def normalize_url(url: str) -> str:
    url = url.strip()
    try:
        parts = urlsplit(url)
    except Exception:
        return url
    path = parts.path.rstrip("/") or parts.path or ""
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            parts.query,
            "",
        )
    )


def bookmark_fingerprint(bookmark: dict[str, Any]) -> str:
    payload = "|".join(
        [
            normalize_url(str(bookmark.get("url") or "")),
            str(bookmark.get("title") or "").strip(),
            str(bookmark.get("description") or "").strip(),
            " ".join(bookmark.get("tags") or []),
            str(bookmark.get("created_at") or ""),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def matches_query(bookmark: dict[str, Any], query: str) -> bool:
    if not query.strip():
        return True
    needle = query.strip().lower()
    haystack = " ".join(
        [
            str(bookmark.get("title") or ""),
            str(bookmark.get("description") or ""),
            str(bookmark.get("extended") or ""),
            str(bookmark.get("url") or ""),
            " ".join(bookmark.get("tags") or []),
        ]
    ).lower()
    return needle in haystack


async def search_bookmarks(
    *,
    client: PinboardClient | None = None,
    query: str = "",
    tag: str | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    pinboard = client or PinboardClient()
    if query.strip() or tag:
        raw_items = await pinboard.list_posts(results=max(top_k * 5, top_k), tag=tag)
    else:
        raw_items = await pinboard.list_recent(count=top_k, tag=tag)

    bookmarks = [normalize_bookmark(item) for item in raw_items]
    bookmarks = [bookmark for bookmark in bookmarks if bookmark.get("url")]
    bookmarks = [bookmark for bookmark in bookmarks if matches_query(bookmark, query)]
    return bookmarks[:top_k]


def bookmark_to_markdown(bookmark: dict[str, Any]) -> str:
    lines = [f"# {bookmark['title']}", "", f"Source: {bookmark['url']}"]
    tags = bookmark.get("tags") or []
    if tags:
        lines.extend(["", f"Tags: {', '.join(tags)}"])
    if bookmark.get("created_at"):
        lines.extend(["", f"Saved: {bookmark['created_at']}"])
    if bookmark.get("description"):
        lines.extend(["", bookmark["description"]])
    return "\n".join(lines).strip()
