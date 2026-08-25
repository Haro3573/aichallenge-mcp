from __future__ import annotations

from aichallenge_mcp.briefing_document import compact_summary, normalized_collection


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
    assert "document" not in summary


def test_normalized_collection_keeps_public_fields_and_omits_raw_transport_payload():
    payload = normalized_collection(collection())

    assert payload["sources"][0]["items"][0]["detail_url"] == "https://example.test/challenge"
    assert payload["sources"][1]["error"] == "collection timed out"
    assert "transport-only" not in str(payload)
    assert "raw" not in str(payload)
