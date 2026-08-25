from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aichallenge_mcp.sources.devpost import (
    LIST_API_URL,
    SOURCE_URL,
    DevpostScrapeResult,
    DevpostSourceAdapter,
    active_devpost_items,
)


FIXTURE = Path(__file__).parent / "fixtures" / "devpost" / "hackathons.json"


def test_fixture_collects_only_open_public_devpost_hackathons_and_preserves_location():
    payload = json.loads(FIXTURE.read_text())

    assert active_devpost_items(payload) == [
        {
            "id": "devpost-30721",
            "title": "Agentic Cinema: The Blockbuster Hackathon",
            "status": "open",
            "location": "Online",
            "submission_period": "Jul 27 - Sep 09, 2026",
            "time_left_to_submission": "16 days left",
            "themes": ["Machine Learning/AI"],
            "prize": "$ 75,000",
            "organizer": "Google",
            "registration_count": 8167,
            "detail_url": "https://agentic-cinema.devpost.com/",
            "source_url": SOURCE_URL,
            "raw": payload["hackathons"][0],
        },
        {
            "id": "devpost-30011",
            "title": "City Builder Weekend",
            "status": "open",
            "location": "New York, NY",
            "submission_period": "Aug 20 - Aug 27, 2026",
            "time_left_to_submission": "2 days left",
            "themes": [],
            "prize": "",
            "organizer": "Devpost",
            "registration_count": 42,
            "detail_url": "https://city-builder-weekend.devpost.com/",
            "source_url": SOURCE_URL,
            "raw": payload["hackathons"][1],
        },
    ]


def test_source_adapter_returns_current_open_source_native_result():
    item = {
        "id": "devpost-30721",
        "title": "Agentic Cinema: The Blockbuster Hackathon",
        "status": "open",
        "location": "Online",
        "detail_url": "https://agentic-cinema.devpost.com/",
        "source_url": SOURCE_URL,
    }

    class StubScraper:
        async def scrape(self):
            return DevpostScrapeResult(
                items=[item],
                source_pages=[SOURCE_URL, LIST_API_URL],
                warnings=[],
            )

    result = asyncio.run(
        DevpostSourceAdapter(
            scraper=StubScraper(),  # type: ignore[arg-type] - source contract test double
            now=lambda: "2026-08-25T05:00:00+00:00",
        ).collect()
    )

    assert result["success"] is True
    assert result["items"] == [item]


def test_source_adapter_treats_listing_failure_as_a_failure_not_an_empty_catalogue():
    class StubScraper:
        async def scrape(self):
            return DevpostScrapeResult(items=[], source_pages=[], warnings=["offline"], listing_failed=True)

    result = asyncio.run(DevpostSourceAdapter(scraper=StubScraper()).collect())  # type: ignore[arg-type]

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: listing API retrieval failed"


def test_source_adapter_rejects_detail_urls_outside_devpost():
    item = {
        "id": "devpost-30721",
        "title": "Untrusted challenge",
        "status": "open",
        "detail_url": "https://example.test/",
        "source_url": SOURCE_URL,
    }

    class StubScraper:
        async def scrape(self):
            return DevpostScrapeResult(items=[item], source_pages=[SOURCE_URL], warnings=[])

    result = asyncio.run(DevpostSourceAdapter(scraper=StubScraper()).collect())  # type: ignore[arg-type]

    assert result["success"] is False
    assert result["error"] == "source contract failed: required fields missing: invalid open item metadata"


def test_mcp_registers_devpost_as_a_public_source_tool():
    from aichallenge_mcp import server

    tools = asyncio.run(server.mcp.list_tools())
    tool = next(tool for tool in tools if tool.name == "collect_devpost_hackathons")

    assert tool.annotations.read_only_hint is True
    assert "open for submissions" in tool.description
