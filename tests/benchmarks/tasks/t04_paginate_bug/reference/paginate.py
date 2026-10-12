"""Pagination helper used by the list screens."""

from __future__ import annotations

from typing import Any


def paginate(items: list[Any], page: int, per_page: int) -> dict[str, Any]:
    """Return one page of `items` (pages count from 1) with paging details.

    Keys: items (this page's slice), page, per_page, total_items, total_pages (the last page may be
    partly filled), has_next (a later page exists), has_prev (an earlier page exists).
    A page beyond the last one returns an empty `items` list and has_next False.
    `page` or `per_page` below 1 raises ValueError.
    """
    if page < 1 or per_page < 1:
        raise ValueError("page and per_page must be at least 1")
    total_pages = -(-len(items) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "page": page,
        "per_page": per_page,
        "total_items": len(items),
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }
