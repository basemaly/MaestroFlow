"""Direct Calibre Content Server client for bounded discovery and preview workflows."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urlencode, urljoin

import httpx


DEFAULT_LIBRARY_ID = "ALL-Clean"
DEFAULT_PREVIEW_LIMIT = 10
DEFAULT_CANDIDATE_LIMIT = 80
_CATEGORY_KEYS = {
    "tags": "tags",
    "kobo_collections": "#kobocollections",
}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "about",
    "all",
    "am",
    "are",
    "as",
    "at",
    "be",
    "book",
    "books",
    "by",
    "describe",
    "find",
    "for",
    "from",
    "get",
    "have",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "looking",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "search",
    "show",
    "that",
    "the",
    "their",
    "them",
    "these",
    "those",
    "to",
    "use",
    "want",
    "with",
}
_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9'_-]*")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _encode_category_key(value: str) -> str:
    return value.encode("utf-8").hex()


def _strip_html(value: str) -> str:
    return unescape(_HTML_TAG_RE.sub(" ", value or " ")).strip()


def _normalize_token(token: str) -> str:
    cleaned = token.casefold().strip(" _-'")
    if len(cleaned) > 4 and cleaned.endswith("ies"):
        return cleaned[:-3] + "y"
    if len(cleaned) > 4 and cleaned.endswith("es"):
        return cleaned[:-2]
    if len(cleaned) > 3 and cleaned.endswith("s"):
        return cleaned[:-1]
    return cleaned


def _tokenize(value: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for raw in _TOKEN_PATTERN.findall(value.casefold()):
        token = _normalize_token(raw)
        if len(token) < 2 or token in _STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _book_collections(book: dict[str, Any]) -> list[str]:
    return (
        book.get("user_metadata", {})
        .get("#kobocollections", {})
        .get("#value#", [])
        or []
    )


def _book_text_fields(book: dict[str, Any]) -> dict[str, str]:
    identifiers = " ".join(str(value) for value in (book.get("identifiers") or {}).values())
    return {
        "title": str(book.get("title") or ""),
        "authors": " ".join(book.get("authors") or []),
        "tags": " ".join(book.get("tags") or []),
        "collections": " ".join(_book_collections(book)),
        "publisher": str(book.get("publisher") or ""),
        "series": str(book.get("series") or ""),
        "comments": _strip_html(str(book.get("comments") or "")),
        "identifiers": identifiers,
    }


def _field_tokens(book: dict[str, Any]) -> dict[str, set[str]]:
    return {field: set(_tokenize(value)) for field, value in _book_text_fields(book).items()}


def _normalize_exact(value: str | None) -> str:
    return (value or "").strip().casefold()


def _matches_exact_filter(book: dict[str, Any], *, field: str, value: str | None) -> bool:
    if not value:
        return True
    target = _normalize_exact(value)
    if field == "author":
        values = book.get("authors") or []
    elif field == "tag":
        values = book.get("tags") or []
    elif field == "kobo_collection":
        values = _book_collections(book)
    elif field == "title":
        values = [book.get("title") or ""]
    elif field == "series":
        values = [book.get("series") or ""]
    elif field == "publisher":
        values = [book.get("publisher") or ""]
    else:
        return True
    return any(_normalize_exact(str(item)) == target for item in values)


def _score_book(book: dict[str, Any], *, query: str | None) -> tuple[float, list[str]]:
    if not query:
        return 0.0, []

    normalized_query = query.casefold().strip()
    tokens = _tokenize(query)
    fields = _book_text_fields(book)
    tokens_by_field = _field_tokens(book)

    score = 0.0
    reasons: list[str] = []

    if normalized_query:
        if normalized_query in fields["title"].casefold():
            score += 20.0
            reasons.append("title phrase")
        if normalized_query in fields["authors"].casefold():
            score += 14.0
            reasons.append("author phrase")
        if normalized_query in fields["tags"].casefold():
            score += 14.0
            reasons.append("tag phrase")
        if normalized_query in fields["collections"].casefold():
            score += 12.0
            reasons.append("collection phrase")
        if normalized_query in fields["comments"].casefold():
            score += 8.0
            reasons.append("description phrase")

    for token in tokens:
        if token in tokens_by_field["title"]:
            score += 6.0
            reasons.append(f"title:{token}")
        if token in tokens_by_field["authors"]:
            score += 5.0
            reasons.append(f"author:{token}")
        if token in tokens_by_field["tags"]:
            score += 5.0
            reasons.append(f"tag:{token}")
        if token in tokens_by_field["collections"]:
            score += 4.0
            reasons.append(f"collection:{token}")
        if token in tokens_by_field["comments"]:
            score += 2.0
            reasons.append(f"description:{token}")

    if tokens:
        matched = {reason.split(":", 1)[-1] for reason in reasons if ":" in reason}
        score += len(matched) * 2.5
    return score, sorted(set(reasons))


@dataclass(frozen=True)
class CalibreServerConfig:
    base_url: str
    library_id: str
    timeout_seconds: float = 20.0
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT

    @classmethod
    def from_env(cls) -> "CalibreServerConfig":
        return cls(
            base_url=os.getenv("CALIBRE_SERVER_BASE_URL", "http://127.0.0.1:9876").rstrip("/"),
            library_id=os.getenv("CALIBRE_SERVER_LIBRARY_ID", DEFAULT_LIBRARY_ID).strip() or DEFAULT_LIBRARY_ID,
            timeout_seconds=float(os.getenv("CALIBRE_SERVER_TIMEOUT_SECONDS", "20")),
            candidate_limit=max(10, int(os.getenv("CALIBRE_SERVER_CANDIDATE_LIMIT", str(DEFAULT_CANDIDATE_LIMIT)))),
        )


class CalibreServerClient:
    def __init__(
        self,
        *,
        config: CalibreServerConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config or CalibreServerConfig.from_env()
        self._transport = transport

    async def _request_json(self, path: str) -> dict[str, Any] | list[Any]:
        async with httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

    async def get_library_info(self) -> dict[str, Any]:
        payload = await self._request_json("/ajax/library-info")
        assert isinstance(payload, dict)
        return payload

    async def list_category_items(
        self,
        *,
        category: str,
        library_id: str | None = None,
    ) -> list[dict[str, Any]]:
        category_key = _CATEGORY_KEYS[category]
        encoded = _encode_category_key(category_key)
        resolved_library = library_id or self.config.library_id
        offset = 0
        page_size = 100
        items: list[dict[str, Any]] = []

        while True:
            path = f"/ajax/category/{encoded}/{resolved_library}?{urlencode({'offset': offset, 'num': page_size})}"
            payload = await self._request_json(path)
            assert isinstance(payload, dict)
            page_items = payload.get("items", [])
            if not isinstance(page_items, list):
                break
            items.extend(item for item in page_items if isinstance(item, dict))
            offset += len(page_items)
            total = int(payload.get("total_num", len(items)) or 0)
            if offset >= total or not page_items:
                break
        return items

    async def find_category_item(
        self,
        *,
        category: str,
        name: str,
        library_id: str | None = None,
    ) -> dict[str, Any] | None:
        target = _normalize_exact(name)
        for item in await self.list_category_items(category=category, library_id=library_id):
            if _normalize_exact(str(item.get("name") or "")) == target:
                return item
        return None

    async def list_book_ids_for_item(self, item_url: str) -> list[int]:
        offset = 0
        page_size = 100
        discovered: list[int] = []
        while True:
            separator = "&" if "?" in item_url else "?"
            path = f"{item_url}{separator}{urlencode({'offset': offset, 'num': page_size})}"
            payload = await self._request_json(path)
            assert isinstance(payload, dict)
            page_ids = payload.get("book_ids", [])
            if not isinstance(page_ids, list):
                break
            discovered.extend(int(book_id) for book_id in page_ids)
            offset += len(page_ids)
            total = int(payload.get("total_num", len(discovered)) or 0)
            if offset >= total or not page_ids:
                break
        return discovered

    async def get_book(self, book_id: int, *, library_id: str | None = None) -> dict[str, Any]:
        resolved_library = library_id or self.config.library_id
        payload = await self._request_json(f"/ajax/book/{book_id}/{resolved_library}")
        assert isinstance(payload, dict)
        payload["_library_id"] = resolved_library
        payload["_detail_url"] = urljoin(
            f"{self.config.base_url}/",
            f"#book_id={book_id}&library_id={resolved_library}",
        )
        return payload

    async def get_books(self, book_ids: list[int], *, library_id: str | None = None) -> list[dict[str, Any]]:
        books: list[dict[str, Any]] = []
        for book_id in book_ids:
            books.append(await self.get_book(book_id, library_id=library_id))
        return books

    async def search_book_ids(
        self,
        *,
        query: str,
        library_id: str | None = None,
        limit: int | None = None,
    ) -> list[int]:
        resolved_library = library_id or self.config.library_id
        offset = 0
        page_size = 100
        discovered: list[int] = []
        while True:
            params = {"query": query, "offset": offset, "num": page_size}
            path = f"/ajax/search?{urlencode(params)}"
            payload = await self._request_json(path)
            assert isinstance(payload, dict)
            if payload.get("library_id") not in (None, resolved_library):
                break
            page_ids = payload.get("book_ids", [])
            if not isinstance(page_ids, list):
                break
            discovered.extend(int(book_id) for book_id in page_ids)
            if limit is not None and len(discovered) >= limit:
                return discovered[:limit]
            offset += len(page_ids)
            total = int(payload.get("total_num", len(discovered)) or 0)
            if offset >= total or not page_ids:
                break
        return discovered

    async def _book_ids_for_exact_filter(
        self,
        *,
        field: str,
        value: str | None,
        library_id: str,
    ) -> set[int] | None:
        if not value:
            return None
        if field == "tag":
            item = await self.find_category_item(category="tags", name=value, library_id=library_id)
            if item and isinstance(item.get("url"), str):
                return set(await self.list_book_ids_for_item(item["url"]))
            return set()
        if field == "kobo_collection":
            item = await self.find_category_item(category="kobo_collections", name=value, library_id=library_id)
            if item and isinstance(item.get("url"), str):
                return set(await self.list_book_ids_for_item(item["url"]))
            return set()

        ids = set()
        for token in _tokenize(value) or [value.strip()]:
            ids.update(await self.search_book_ids(query=token, library_id=library_id, limit=self.config.candidate_limit))
        return ids

    async def _candidate_book_ids(
        self,
        *,
        query: str | None,
        title: str | None,
        author: str | None,
        tag: str | None,
        kobo_collection: str | None,
        series: str | None,
        publisher: str | None,
        library_id: str,
    ) -> list[int]:
        intersections: list[set[int]] = []

        for field, value in (
            ("tag", tag),
            ("kobo_collection", kobo_collection),
            ("title", title),
            ("author", author),
            ("series", series),
            ("publisher", publisher),
        ):
            ids = await self._book_ids_for_exact_filter(field=field, value=value, library_id=library_id)
            if ids is not None:
                intersections.append(ids)

        token_queries = []
        if query:
            token_queries.extend(_tokenize(query))
        for value in (title, author, series, publisher):
            if value:
                token_queries.extend(_tokenize(value))

        if token_queries:
            ranked_hits: dict[int, int] = {}
            first_seen: dict[int, int] = {}
            counter = 0
            for token in token_queries[:12]:
                ids = await self.search_book_ids(query=token, library_id=library_id, limit=self.config.candidate_limit)
                for book_id in ids:
                    ranked_hits[book_id] = ranked_hits.get(book_id, 0) + 1
                    if book_id not in first_seen:
                        first_seen[book_id] = counter
                        counter += 1
            ordered = sorted(ranked_hits, key=lambda book_id: (-ranked_hits[book_id], first_seen[book_id]))
            if ordered:
                intersections.append(set(ordered))
        if not intersections:
            raise ValueError("At least one of `query`, `title`, `author`, `tag`, `kobo_collection`, `series`, or `publisher` must be provided")

        candidate_ids = set.intersection(*intersections)
        if not candidate_ids:
            return []

        if token_queries:
            ordered_ids = [book_id for book_id in ordered if book_id in candidate_ids]
        else:
            ordered_ids = sorted(candidate_ids)
        return ordered_ids[: self.config.candidate_limit]

    async def discover_books(
        self,
        *,
        query: str | None = None,
        title: str | None = None,
        author: str | None = None,
        tag: str | None = None,
        kobo_collection: str | None = None,
        series: str | None = None,
        publisher: str | None = None,
        calibre_ids: list[int] | None = None,
        library_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        resolved_library = library_id or self.config.library_id
        if calibre_ids:
            books = await self.get_books(calibre_ids, library_id=resolved_library)
        else:
            candidate_ids = await self._candidate_book_ids(
                query=query,
                title=title,
                author=author,
                tag=tag,
                kobo_collection=kobo_collection,
                series=series,
                publisher=publisher,
                library_id=resolved_library,
            )
            books = await self.get_books(candidate_ids, library_id=resolved_library)

        filtered: list[tuple[float, dict[str, Any]]] = []
        for book in books:
            if not _matches_exact_filter(book, field="title", value=title):
                continue
            if not _matches_exact_filter(book, field="author", value=author):
                continue
            if not _matches_exact_filter(book, field="tag", value=tag):
                continue
            if not _matches_exact_filter(book, field="kobo_collection", value=kobo_collection):
                continue
            if not _matches_exact_filter(book, field="series", value=series):
                continue
            if not _matches_exact_filter(book, field="publisher", value=publisher):
                continue

            score, reasons = _score_book(book, query=query)
            if query and score <= 0:
                continue
            book["_match_score"] = score
            book["_match_reasons"] = reasons
            filtered.append((score, book))

        if query:
            filtered.sort(
                key=lambda item: (
                    -item[0],
                    str(item[1].get("title") or "").casefold(),
                    int(item[1].get("application_id") or 0),
                )
            )
        else:
            filtered.sort(
                key=lambda item: (
                    str(item[1].get("title") or "").casefold(),
                    int(item[1].get("application_id") or 0),
                )
            )
        return [book for _, book in filtered[: (limit or DEFAULT_PREVIEW_LIMIT)]]
