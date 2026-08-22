from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from aichallenge_mcp.sources.kaggle import (
    SOURCE_URL,
    KaggleScrapeResult,
    KaggleSourceAdapter,
    current_online_items,
    format_reward,
)


FIXTURE = Path(__file__).parent / "fixtures" / "kaggle" / "competitions.json"


def test_fixture_collects_only_active_online_kaggle_competitions():
    items = json.loads(FIXTURE.read_text())

    result = current_online_items(items, datetime(2026, 8, 22, tzinfo=timezone.utc))

    assert result == [
        {
            "id": "kaggle-147734",
            "title": "Kaggriculture",
            "status": "active",
            "location": "Online",
            "participation_mode": "online",
            "deadline": "2026-09-30T23:59:00Z",
            "description": "Create an agent to play in this farming simulation.",
            "organizer": "Kaggle",
            "participant_count": 5818,
            "prize": "$50,000",
            "categories": ["Simulation Competition"],
            "detail_url": "https://www.kaggle.com/competitions/kaggriculture",
            "source_url": SOURCE_URL,
            "raw": items[0],
        }
    ]


def test_formats_structured_kaggle_reward():
    assert format_reward({"id": "USD", "quantity": 50000}) == "$50,000"


def test_source_adapter_returns_online_only_source_native_result():
    item = {
        "id": "kaggle-147734",
        "title": "Kaggriculture",
        "status": "active",
        "location": "Online",
        "participation_mode": "online",
        "deadline": "2026-09-30T23:59:00Z",
        "detail_url": "https://www.kaggle.com/competitions/kaggriculture",
        "source_url": SOURCE_URL,
    }

    class StubScraper:
        async def scrape(self):
            return KaggleScrapeResult(items=[item], source_pages=[SOURCE_URL], warnings=[])

    result = asyncio.run(
        KaggleSourceAdapter(
            scraper=StubScraper(),  # type: ignore[arg-type] - source contract test double
            now=lambda: "2026-08-22T09:30:00+00:00",
        ).collect()
    )

    assert result["success"] is True
    assert result["items"] == [item]


def test_source_adapter_treats_listing_failure_as_a_failure_not_an_empty_catalogue():
    class StubScraper:
        async def scrape(self):
            return KaggleScrapeResult(items=[], source_pages=[], warnings=["offline"], listing_failed=True)

    result = asyncio.run(KaggleSourceAdapter(scraper=StubScraper()).collect())  # type: ignore[arg-type]

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: listing page retrieval failed"


def test_mcp_registers_kaggle_as_a_public_source_tool():
    from aichallenge_mcp import server

    tools = asyncio.run(server.mcp.list_tools())
    tool = next(tool for tool in tools if tool.name == "collect_kaggle_competitions")

    assert tool.annotations.read_only_hint is True
    assert "Online location only" in tool.description
