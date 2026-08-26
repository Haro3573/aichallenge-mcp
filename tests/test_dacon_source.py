from __future__ import annotations

import asyncio
from pathlib import Path

from bs4 import BeautifulSoup

from aichallenge_mcp.sources.dacon import (
    SOURCE_URL,
    DaconScraper,
    DaconScrapeResult,
    DaconSourceAdapter,
    extract_detail_fields,
    extract_listing_items,
)


FIXTURES = Path(__file__).parent / "fixtures" / "dacon"


def test_detail_pages_are_fetched_with_bounded_concurrency(monkeypatch):
    monkeypatch.setenv("DACON_DETAIL_CONCURRENCY", "2")
    listing = "".join(
        (
            '<div class="comp">'
                f'<a href="/competitions/official/2367{index}/overview/">'
                f'<span class="name">테스트 대회 {index}</span>'
                '<span class="dday">진행중</span>'
                '<span class="info2">알고리즘</span>'
                '<span class="joinTeam">1명</span>'
                '</a>'
            '</div>'
        )
        for index in range(4)
    )
    active = 0
    peak = 0

    async def fake_fetch(_client, url: str) -> str:
        nonlocal active, peak
        if url == SOURCE_URL:
            return listing
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.01)
            return "대회 주요 일정 2026-08-01 개요"
        finally:
            active -= 1

    scraper = DaconScraper()
    monkeypatch.setattr(scraper, "fetch_html", fake_fetch)

    result = asyncio.run(scraper.scrape())

    assert peak == 2
    assert [item["schedule"] for item in result.items] == ["2026-08-01"] * 4
    assert result.warnings == []


def test_listing_fixture_collects_only_currently_actionable_competitions():
    items = extract_listing_items(BeautifulSoup((FIXTURES / "competitions.html").read_text(), "html.parser"))

    assert items == [
        {
            "id": "dacon-236749",
            "title": "딥보이스 범죄 대응을 위한 AI 탐지 모델 경진대회",
            "status": "참가신청중",
            "tags": ["알고리즘", "코드 제출 평가", "오디오", "딥보이스"],
            "participant_count": 222,
            "detail_url": "https://dacon.io/competitions/official/236749/overview/",
            "source_url": SOURCE_URL,
            "raw_text": "딥보이스 범죄 대응을 위한 AI 탐지 모델 경진대회 알고리즘 | 코드 제출 평가 | 오디오 | 딥보이스 참가신청중 222명",
        },
        {
            "id": "dacon-236753",
            "title": "블랙박스 영상 기반 지능형 고의사고 분석 모델 AI 경진대회",
            "status": "연습",
            "tags": ["알고리즘", "컴퓨터비전", "고의교통사고"],
            "participant_count": 1191,
            "detail_url": "https://dacon.io/competitions/official/236753/overview/",
            "source_url": SOURCE_URL,
            "raw_text": "블랙박스 영상 기반 지능형 고의사고 분석 모델 AI 경진대회 알고리즘 | 컴퓨터비전 | 고의교통사고 연습 1,191명",
        },
    ]


def test_detail_fixture_extracts_optional_public_fields():
    fields = extract_detail_fields(BeautifulSoup((FIXTURES / "detail.html").read_text(), "html.parser"))

    assert fields == {
        "prize": "상금 4,200만 원",
        "audience": "대한민국 국민 누구나",
        "organizer": "주최: 한국인터넷진흥원 / 운영: DACON",
        "schedule": "08.18 참가 신청 시작 08.26 대회 시작",
    }


def test_source_adapter_returns_source_native_result_with_detail_fields():
    item = {
        "id": "dacon-236749",
        "title": "AI 경진대회",
        "status": "참가신청중",
        "detail_url": "https://dacon.io/competitions/official/236749/overview/",
        "source_url": SOURCE_URL,
        "tags": ["알고리즘"],
        "participant_count": 222,
        "prize": "상금 4,200만 원",
    }

    class StubScraper:
        async def scrape(self):
            return DaconScrapeResult(items=[item], source_pages=[SOURCE_URL], warnings=[])

    result = asyncio.run(
        DaconSourceAdapter(
            scraper=StubScraper(),  # type: ignore[arg-type] - source contract test double
            now=lambda: "2026-08-22T08:00:00+00:00",
        ).collect()
    )

    assert result["success"] is True
    assert result["items"] == [item]
    assert result["source_pages"] == [SOURCE_URL]


def test_source_adapter_treats_listing_failure_as_a_failure_not_an_empty_catalogue():
    class StubScraper:
        async def scrape(self):
            return DaconScrapeResult(items=[], source_pages=[], warnings=["offline"], listing_failed=True)

    result = asyncio.run(DaconSourceAdapter(scraper=StubScraper()).collect())  # type: ignore[arg-type]

    assert result["success"] is False
    assert result["items"] == []
    assert result["error"] == "source contract failed: listing page retrieval failed"


def test_mcp_registers_dacon_as_a_public_source_tool():
    from aichallenge_mcp import server

    tools = asyncio.run(server.mcp.list_tools())
    tool = next(tool for tool in tools if tool.name == "collect_dacon_competitions")

    assert tool.annotations.read_only_hint is True
    assert "current public, actionable DACON" in tool.description
