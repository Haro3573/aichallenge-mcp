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


def compact_collection(collection: Mapping[str, Any]) -> dict[str, Any]:
    """Encode every normalized item once as a source-local columnar table.

    This is lossless relative to :func:`normalized_collection`: source metadata
    and every public item field remain present, but repeated JSON object keys
    are moved into one ``item_columns`` list per source.  It reduces the model
    context required for a large, fresh collection without turning the MCP
    server into a document renderer.
    """
    normalized = normalized_collection(collection)
    if not isinstance(normalized, Mapping):
        return {"format": "aichallenge-mcp.columnar.v1", "sources": []}

    compact_sources: list[dict[str, Any]] = []
    for source in normalized.get("sources", []):
        if not isinstance(source, Mapping):
            continue
        items = source.get("items", [])
        valid_items = [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []
        columns = sorted({key for item in valid_items for key in item})
        compact_sources.append(
            {
                **{key: value for key, value in source.items() if key != "items"},
                "item_columns": columns,
                "item_rows": [[item.get(column) for column in columns] for item in valid_items],
            }
        )

    return {
        **{key: value for key, value in normalized.items() if key != "sources"},
        "format": "aichallenge-mcp.columnar.v1",
        "sources": compact_sources,
    }


def expand_compact_collection(collection: Mapping[str, Any]) -> dict[str, Any]:
    """Expand a columnar collection for tests and consumers needing item maps."""
    expanded_sources: list[dict[str, Any]] = []
    for source in collection.get("sources", []):
        if not isinstance(source, Mapping):
            continue
        columns = source.get("item_columns", [])
        rows = source.get("item_rows", [])
        if not isinstance(columns, list) or not isinstance(rows, list):
            continue
        items = [
            {column: row[index] for index, column in enumerate(columns) if index < len(row)}
            for row in rows
            if isinstance(row, list)
        ]
        expanded_sources.append(
            {
                **{
                    key: value
                    for key, value in source.items()
                    if key not in {"item_columns", "item_rows"}
                },
                "items": items,
            }
        )
    return {
        **{
            key: value
            for key, value in collection.items()
            if key not in {"format", "sources"}
        },
        "sources": expanded_sources,
    }
