"""Ephemeral, human-readable documents for a single collection run.

The server deliberately does not write these documents to disk.  A caller can
receive the Markdown through MCP tool-result metadata and choose to download it
from the companion MCP App UI.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


def document_filename(collection: Mapping[str, Any]) -> str:
    """Return a safe, informative filename for one collection run."""
    checked_at = str(collection.get("checked_at") or "")
    if not checked_at:
        return "ai-contest-briefing-current.md"
    try:
        parsed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        safe_timestamp = parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    except ValueError:
        safe_timestamp = "".join(char for char in checked_at if char.isalnum())
    return f"ai-contest-briefing-{safe_timestamp or 'current'}.md"


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
        "document": {
            "file_name": document_filename(collection),
            "mime_type": "text/markdown;charset=utf-8",
        },
    }


def _display_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def render_markdown_document(collection: Mapping[str, Any]) -> str:
    """Render the complete normalized collection as a Markdown download.

    ``raw`` payloads are intentionally omitted: they are transport/debug data,
    can dwarf the useful normalized fields, and do not add information needed by
    an operator reading the briefing.
    """
    counts = collection.get("counts", {})
    if not isinstance(counts, Mapping):
        counts = {}
    lines = [
        "# AI 대회 브리핑",
        "",
        f"- 수집 시각: {collection.get('checked_at', '-')}",
        f"- source 성공: {counts.get('succeeded', 0)}/{counts.get('total', 0)}",
        f"- source 실패: {counts.get('failed', 0)}",
        "- 범위: 운영자가 등록한 공개 source의 이번 수집 결과",
        "",
    ]

    sources = collection.get("sources", [])
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, Mapping):
            continue
        source_name = source.get("source_name") or source.get("source_id") or "알 수 없는 source"
        lines.extend(
            [
                f"## {source_name}",
                "",
                f"- Source ID: {source.get('source_id', '-')}",
                f"- 원본 URL: {source.get('source_url', '-')}",
                f"- 수집 상태: {'성공' if source.get('success') else '실패'}",
                f"- 시도 횟수: {source.get('attempts', '-')}",
            ]
        )
        warnings = source.get("warnings", [])
        if warnings:
            lines.append(f"- 경고: {_display_value(warnings)}")
        if source.get("error"):
            lines.append(f"- 오류: {source['error']}")

        items = source.get("items", [])
        if not source.get("success"):
            lines.extend(["", "수집에 실패했으므로 이 source의 부재나 마감을 추론하지 마세요.", ""])
            continue
        if not isinstance(items, list) or not items:
            lines.extend(["", "정상 결과 항목이 없습니다.", ""])
            continue

        lines.extend(["", f"### 항목 ({len(items)}건)", ""])
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                lines.extend([f"{index}. {_display_value(item)}", ""])
                continue
            title = item.get("title") or item.get("name") or f"항목 {index}"
            lines.extend([f"#### {index}. {title}", ""])
            for key, value in item.items():
                if key in {"title", "name", "raw"}:
                    continue
                lines.append(f"- {key}: {_display_value(value)}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
