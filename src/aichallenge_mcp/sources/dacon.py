from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..models import utc_now_iso
from .result import source_result


SOURCE_URL = "https://dacon.io/competitions"
DETAIL_PATH_RE = re.compile(r"^/competitions/official/(?P<id>\d+)/overview/?$")
ACTIVE_STATUSES = frozenset({"참가신청중", "진행중", "연습"})


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_listing_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extract only currently actionable official Dacon competition cards."""
    items: list[dict[str, Any]] = []
    for card in soup.select("div.comp"):
        anchor = card.select_one("a[href]")
        if anchor is None:
            continue

        path = anchor.get("href", "")
        match = DETAIL_PATH_RE.fullmatch(path)
        if match is None:
            continue

        title = clean((card.select_one(".name") or anchor).get_text(" ", strip=True))
        status = clean((card.select_one(".dday") or "").get_text(" ", strip=True))
        if not title or status not in ACTIVE_STATUSES:
            continue

        tags_text = clean((card.select_one(".info2") or "").get_text(" ", strip=True))
        participants_text = clean((card.select_one(".joinTeam") or "").get_text(" ", strip=True))
        participants = re.search(r"([\d,]+)명", participants_text)
        detail_url = urljoin(SOURCE_URL, path)
        items.append(
            {
                "id": f"dacon-{match.group('id')}",
                "title": title,
                "status": status,
                "tags": [tag.strip() for tag in tags_text.split("|") if tag.strip()],
                "participant_count": int(participants.group(1).replace(",", "")) if participants else None,
                "detail_url": detail_url,
                "source_url": SOURCE_URL,
                "raw_text": clean(card.get_text(" ", strip=True)),
            }
        )
    return items


def extract_detail_fields(soup: BeautifulSoup) -> dict[str, str]:
    """Extract optional public fields from one Dacon overview page."""
    page_text = clean(soup.get_text(" ", strip=True))

    def after(label: str, stops: tuple[str, ...]) -> str:
        stop_pattern = "|".join(re.escape(stop) for stop in stops)
        match = re.search(r"(?:\[\s*)?" + re.escape(label) + r"(?:\s*\])?\s*[:：]?\s*(.*?)(?=" + stop_pattern + r"|$)", page_text)
        return clean(match.group(1)).rstrip("[").rstrip() if match else ""

    prize = re.search(r"상금\s*([\d,]+\s*(?:만\s*원|원))", page_text)
    return {
        "prize": clean(f"상금 {prize.group(1)}") if prize else "",
        "audience": after("참가 자격", ("주최 / 운영", "주최/운영", "문의", "대회 일정")),
        "organizer": after("주최 / 운영", ("대회 주요 일정", "대회 일정", "문의", "규칙", "개요", "평가")),
        "schedule": after("대회 주요 일정", ("개요", "평가", "규칙", "상금")),
    }


@dataclass(slots=True)
class DaconScrapeResult:
    items: list[dict[str, Any]]
    source_pages: list[str]
    warnings: list[str]
    listing_failed: bool = False


class DaconScraper:
    def __init__(self) -> None:
        self._timeout = float(os.getenv("DACON_TIMEOUT", "20"))
        self._user_agent = os.getenv(
            "DACON_USER_AGENT",
            "aichallenge-mcp/0.1 (+https://dacon.io/competitions)",
        )

    async def fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text

    async def scrape(self) -> DaconScrapeResult:
        warnings: list[str] = []
        source_pages: list[str] = []
        headers = {"User-Agent": self._user_agent}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            try:
                listing_html = await self.fetch_html(client, SOURCE_URL)
            except Exception as exc:  # noqa: BLE001 - failure is returned as source data
                return DaconScrapeResult(
                    items=[],
                    source_pages=[],
                    warnings=[f"목록 페이지 수집 실패: {SOURCE_URL} ({exc})"],
                    listing_failed=True,
                )

            source_pages.append(SOURCE_URL)
            items = extract_listing_items(BeautifulSoup(listing_html, "html.parser"))
            for item in items:
                try:
                    detail_html = await self.fetch_html(client, item["detail_url"])
                    item.update(extract_detail_fields(BeautifulSoup(detail_html, "html.parser")))
                    source_pages.append(item["detail_url"])
                except Exception as exc:  # noqa: BLE001 - a detail warning preserves the listing item
                    warnings.append(f"상세 페이지 수집 실패: {item['detail_url']} ({exc})")

        return DaconScrapeResult(
            items=items,
            source_pages=source_pages,
            warnings=warnings,
        )


class DaconSourceAdapter:
    """Collect public, currently actionable official Dacon competitions."""

    source_id = "dacon_competitions"
    source_name = "DACON Competitions"
    source_url = SOURCE_URL
    required_item_fields = ("id", "title", "status", "detail_url", "source_url")

    def __init__(
        self,
        scraper: DaconScraper | None = None,
        now: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._scraper = scraper or DaconScraper()
        self._now = now

    async def collect(self) -> dict[str, Any]:
        checked_at = self._now()
        try:
            result = await self._scraper.scrape()
        except Exception as exc:  # noqa: BLE001 - source failures are public result data
            return self._failure(checked_at, [], [], f"collection failed: {exc}")

        if not isinstance(result, DaconScrapeResult):
            return self._failure(checked_at, [], [], "source contract failed: invalid scraper result")
        if result.listing_failed:
            return self._failure(
                checked_at,
                result.source_pages,
                result.warnings,
                "source contract failed: listing page retrieval failed",
            )
        if not self._valid_metadata(result.source_pages, result.warnings):
            return self._failure(checked_at, [], [], "source contract failed: invalid scraper result")
        if not result.items:
            return self._failure(
                checked_at,
                result.source_pages,
                result.warnings,
                "source contract failed: no active Dacon competitions collected",
            )
        if not all(isinstance(item, dict) for item in result.items):
            return self._failure(
                checked_at,
                result.source_pages,
                result.warnings,
                "source contract failed: invalid item shape",
            )

        missing_fields = sorted(
            {
                field
                for item in result.items
                for field in self.required_item_fields
                if not item.get(field)
            }
        )
        if missing_fields or not all(self._is_dacon_url(item["detail_url"]) for item in result.items):
            detail = ", ".join(missing_fields) if missing_fields else "invalid item source URL"
            return self._failure(
                checked_at,
                result.source_pages,
                result.warnings,
                f"source contract failed: required fields missing: {detail}",
            )

        return source_result(
            source_id=self.source_id,
            source_name=self.source_name,
            source_url=self.source_url,
            checked_at=checked_at,
            success=True,
            items=result.items,
            source_pages=sorted(set(result.source_pages)),
            warnings=result.warnings,
            error=None,
        )

    def _failure(
        self,
        checked_at: str,
        source_pages: list[str],
        warnings: list[str],
        error: str,
    ) -> dict[str, Any]:
        return source_result(
            source_id=self.source_id,
            source_name=self.source_name,
            source_url=self.source_url,
            checked_at=checked_at,
            success=False,
            items=[],
            source_pages=source_pages,
            warnings=warnings,
            error=error,
        )

    @staticmethod
    def _is_dacon_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value)
        return parsed.scheme == "https" and parsed.netloc in {"dacon.io", "www.dacon.io"}

    @classmethod
    def _valid_metadata(cls, source_pages: list[str], warnings: list[str]) -> bool:
        return all(cls._is_dacon_url(page) for page in source_pages) and all(
            isinstance(warning, str) for warning in warnings
        )
