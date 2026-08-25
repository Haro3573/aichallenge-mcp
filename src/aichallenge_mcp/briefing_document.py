"""Conversation-safe summaries and normalized data for one collection run.

The MCP server provides data only.  Rendering a document from that data is a
ChatGPT responsibility, not a server-side concern.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def compact_summary(collection: Mapping[str, Any]) -> dict[str, Any]:
    """Return only enough context to brief the conversation without item dumps."""
    sources = collection.get("sources", [])
    source_summaries: list[dict[str, Any]] = []
    total_items = 0

    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, Mapping):
            continue
        items = source.get("items", [])
        item_count = len(items) if isinstance(items, list) else 0
        total_items += item_count
        source_summaries.append(
            {
                "source_id": source.get("source_id"),
                "source_name": source.get("source_name"),
                "source_url": source.get("source_url"),
                "success": source.get("success"),
                "item_count": item_count,
                "attempts": source.get("attempts"),
                "warnings": source.get("warnings", []),
                "error": source.get("error"),
            }
        )

    return {
        "checked_at": collection.get("checked_at"),
        "counts": collection.get("counts", {}),
        "item_count": total_items,
        "sources": source_summaries,
    }


def normalized_collection(collection: Any) -> Any:
    """Return complete model-ready collection data without transport internals.

    Adapters may retain an item-level ``raw`` payload for parser diagnostics.
    It is not part of this plugin's public information contract and may be much
    larger than the useful normalized fields, so it is removed recursively.
    """
    if isinstance(collection, Mapping):
        return {
            key: normalized_collection(value)
            for key, value in collection.items()
            if key != "raw"
        }
    if isinstance(collection, list):
        return [normalized_collection(value) for value in collection]
    if isinstance(collection, tuple):
        return [normalized_collection(value) for value in collection]
    return collection
