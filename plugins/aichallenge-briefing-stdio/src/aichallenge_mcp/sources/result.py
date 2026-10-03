from __future__ import annotations

from typing import Any


def source_result(
    *,
    source_id: str,
    source_name: str,
    source_url: str,
    checked_at: str,
    success: bool,
    items: list[dict[str, Any]],
    source_pages: list[str],
    warnings: list[str],
    error: str | None,
) -> dict[str, Any]:
    """Build the shared audit envelope around a source-native item payload."""
    return {
        "source_id": source_id,
        "source_name": source_name,
        "source_url": source_url,
        "checked_at": checked_at,
        "success": success,
        "items": items,
        "source_pages": source_pages,
        "warnings": warnings,
        "error": error,
    }
