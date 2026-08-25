from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from aichallenge_mcp.sources.kaggle import (
    LIST_API_URL,
    SOURCE_URL,
    KaggleScrapeResult,
    KaggleScraper,
    KaggleSourceAdapter,
    current_online_items,
    format_reward,
    resolve_credentials,
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
            "categories": ["Simulation Competition", "Agents"],
            "detail_url": "https://www.kaggle.com/competitions/kaggriculture",
            "source_url": SOURCE_URL,
        }
    ]
    assert "raw" not in result[0]


def test_formats_structured_kaggle_reward():
    assert format_reward({"id": "USD", "quantity": 50000}) == "$50,000"


def test_uses_access_token_before_legacy_key_pair():
    credentials = resolve_credentials(
        {
            "KAGGLE_API_TOKEN": "test-access-token",
            "KAGGLE_USERNAME": "test-user",
            "KAGGLE_KEY": "test-key",
        }
    )

    assert credentials is not None
    assert credentials.method == "access-token"
    assert credentials.username is None


def test_requires_a_complete_legacy_key_pair():
    assert resolve_credentials({"KAGGLE_USERNAME": "test-user"}) is None
    credentials = resolve_credentials({"KAGGLE_USERNAME": "test-user", "KAGGLE_KEY": "test-key"})
    assert credentials is not None
    assert credentials.method == "legacy-api-key"


def test_scraper_passes_access_token_to_official_client_and_sanitizes_personal_fields():
    requested = []
    client_kwargs = {}

    class Response:
        competitions = json.loads(FIXTURE.read_text())
        next_page_token = ""

    class Client:
        class Competitions:
            class CompetitionApi:
                def list_competitions(self, request):
                    requested.append(request)
                    return Response()

            competition_api_client = CompetitionApi()

        competitions = Competitions()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

    def factory(**kwargs):
        client_kwargs.update(kwargs)
        return Client()

    result = asyncio.run(
        KaggleScraper(
            environ={"KAGGLE_API_TOKEN": "test-access-token"},
            client_factory=factory,
        ).scrape()
    )

    assert result.listing_failed is False
    assert result.source_pages == [SOURCE_URL, LIST_API_URL]
    assert client_kwargs == {
        "api_token": "test-access-token",
        "user_agent": "aichallenge-mcp/0.1 (+https://www.kaggle.com/competitions)",
    }
    assert requested[0].page_size == 100
    assert result.items[0]["id"] == "kaggle-147734"
    assert "user_has_entered" not in result.items[0]
    assert "user_rank" not in result.items[0]


def test_scraper_reports_missing_credentials_as_a_failure_not_an_empty_catalogue():
    result = asyncio.run(KaggleScraper(environ={}).scrape())

    assert result.listing_failed is True
    assert result.items == []
    assert result.source_pages == [SOURCE_URL]
    assert "KAGGLE_API_TOKEN" in result.warnings[0]


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
            return KaggleScrapeResult(items=[item], source_pages=[SOURCE_URL, LIST_API_URL], warnings=[])

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
            return KaggleScrapeResult(items=[], source_pages=[SOURCE_URL], warnings=["credentials missing"], listing_failed=True)

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
    assert "KAGGLE_API_TOKEN" in tool.description
