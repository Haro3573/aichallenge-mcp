from __future__ import annotations

import asyncio
import json

from aichallenge_mcp.models import Competition
from aichallenge_mcp.scraper import ScrapeResult
from aichallenge_mcp.sources.aichallenge4all import Aichallenge4allSourceAdapter


class StubScraper:
    def __init__(self, result: ScrapeResult | Exception) -> None:
        self.result = result

    async def scrape(self) -> ScrapeResult:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def collect(source: Aichallenge4allSourceAdapter) -> dict:
    return asyncio.run(source.collect())


def test_collect_returns_current_source_native_items_and_audit_metadata():
    contest = Competition(
        id="contest-1",
        title="AI 해커톤",
        status="접수중",
        source_url="https://aichallenge4all.or.kr/university",
    )
    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(
            ScrapeResult(
                items=[contest],
                sources=["https://aichallenge4all.or.kr/university"],
                warnings=["상세 페이지 수집 실패"],
            )
        ),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    assert collect(source) == {
        "source_id": "aichallenge4all",
        "source_name": "AI Challenge for All",
        "source_url": "https://aichallenge4all.or.kr",
        "checked_at": "2026-08-22T05:30:00+00:00",
        "success": True,
        "items": [contest.to_dict()],
        "source_pages": ["https://aichallenge4all.or.kr/university"],
        "warnings": ["상세 페이지 수집 실패"],
        "error": None,
    }


def test_collect_treats_no_valid_items_as_source_failure():
    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(ScrapeResult(items=[], sources=["https://example.test"], warnings=[])),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    result = collect(source)

    assert result["success"] is False
    assert result["items"] == []
    assert result["source_pages"] == ["https://example.test"]
    assert result["error"] == "source contract failed: no valid items collected"


def test_collect_treats_missing_required_item_fields_as_source_failure():
    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(
            ScrapeResult(
                items=[Competition(id="contest-1", title="", status="접수중")],
                sources=["https://example.test"],
                warnings=[],
            )
        ),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    result = collect(source)

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: required fields missing: source_url, title"


def test_collect_treats_invalid_native_item_shape_as_source_failure():
    class InvalidItem:
        def to_dict(self):
            return []

    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(
            ScrapeResult(  # type: ignore[arg-type] - verifies a malformed scraper contract
                items=[InvalidItem()],
                sources=["https://example.test"],
                warnings=[],
            )
        ),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    result = collect(source)

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: invalid item shape"


def test_collect_treats_invalid_scraper_metadata_as_source_failure():
    contest = Competition(
        id="contest-1",
        title="AI 해커톤",
        status="접수중",
        source_url="https://aichallenge4all.or.kr/university",
    )
    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(
            ScrapeResult(  # type: ignore[arg-type] - verifies a malformed scraper contract
                items=[contest],
                sources=[123],
                warnings=[],
            )
        ),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    result = collect(source)

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: invalid scraper result"


def test_collect_treats_listing_page_retrieval_error_as_source_failure():
    contest = Competition(
        id="contest-1",
        title="AI 해커톤",
        status="접수중",
        source_url="https://aichallenge4all.or.kr/university",
    )
    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(
            ScrapeResult(
                items=[contest],
                sources=["https://aichallenge4all.or.kr/university"],
                warnings=["일시적인 목록 수집 오류"],
                failed_listing_pages=["https://aichallenge4all.or.kr/moduai"],
            )
        ),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    result = collect(source)

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: listing page retrieval failed"


def test_collect_treats_item_serialization_error_as_source_failure():
    class ExplodingItem:
        def to_dict(self):
            raise ValueError("unexpected shape")

    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(
            ScrapeResult(  # type: ignore[arg-type] - verifies a malformed scraper contract
                items=[ExplodingItem()],
                sources=["https://example.test"],
                warnings=[],
            )
        ),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    result = collect(source)

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: invalid scraper result"


def test_collect_converts_scraper_error_into_source_failure():
    source = Aichallenge4allSourceAdapter(
        scraper=StubScraper(RuntimeError("network unavailable")),
        now=lambda: "2026-08-22T05:30:00+00:00",
    )

    result = collect(source)

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "collection failed: network unavailable"


def test_mcp_source_tool_exposes_the_source_collection_contract(monkeypatch):
    from aichallenge_mcp import server

    class StubSource:
        async def collect(self):
            return {"source_id": "aichallenge4all", "success": True, "items": [{"title": "AI 해커톤"}]}

    monkeypatch.setattr(server, "aichallenge4all_source", StubSource())

    assert json.loads(asyncio.run(server.collect_aichallenge4all())) == {
        "source_id": "aichallenge4all",
        "success": True,
        "items": [{"title": "AI 해커톤"}],
    }


def test_mcp_registers_aichallenge4all_as_a_public_source_tool():
    from aichallenge_mcp import server

    tools = asyncio.run(server.mcp.list_tools())
    tool = next(tool for tool in tools if tool.name == "collect_aichallenge4all")

    assert tool.annotations.read_only_hint is True
    assert "current public AI Challenge for All source" in tool.description
