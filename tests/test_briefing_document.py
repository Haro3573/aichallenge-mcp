from __future__ import annotations

from aichallenge_mcp.briefing_document import compact_summary, document_filename, render_markdown_document


def collection() -> dict:
    return {
        "checked_at": "2026-08-25T10:30:00+00:00",
        "counts": {"total": 2, "succeeded": 1, "failed": 1},
        "sources": [
            {
                "source_id": "example",
                "source_name": "Example contests",
                "source_url": "https://example.test",
                "success": True,
                "attempts": 1,
                "warnings": ["public detail missing"],
                "error": None,
                "items": [
                    {
                        "title": "Example Challenge",
                        "detail_url": "https://example.test/challenge",
                        "status": "open",
                        "tags": ["AI", "online"],
                        "raw": {"oversized": "transport-only"},
                    }
                ],
            },
            {
                "source_id": "broken",
                "source_name": "Broken source",
                "source_url": "https://broken.test",
                "success": False,
                "attempts": 2,
                "warnings": [],
                "error": "collection timed out",
                "items": [],
            },
        ],
    }


def test_compact_summary_excludes_item_payloads_but_keeps_collection_status():
    summary = compact_summary(collection())

    assert summary["item_count"] == 1
    assert summary["sources"][0]["item_count"] == 1
    assert "items" not in summary["sources"][0]
    assert "raw" not in str(summary)
    assert summary["document"]["file_name"] == "ai-contest-briefing-20260825T103000Z.md"


def test_markdown_document_keeps_normalized_fields_and_omits_raw_transport_payload():
    document = render_markdown_document(collection())

    assert document.startswith("# AI 대회 브리핑")
    assert "## Example contests" in document
    assert "#### 1. Example Challenge" in document
    assert "- detail_url: https://example.test/challenge" in document
    assert "collection timed out" in document
    assert "수집에 실패했으므로" in document
    assert "transport-only" not in document
    assert "raw:" not in document


def test_filename_falls_back_to_current_for_missing_collection_time():
    assert document_filename({}) == "ai-contest-briefing-current.md"
