from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from ..models import utc_now_iso
from .result import source_result


SOURCE_URL = "https://www.kaggle.com/competitions"
LIST_API_URL = "https://www.kaggle.com/api/i/competitions.CompetitionService/ListCompetitions"
PAGE_SIZE = 100
MAXIMUM_PAGES = 20
OFFLINE_MARKERS = ("in-person", "in person", "on-site", "onsite", "offline")


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_reward(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    quantity = value.get("quantity")
    currency = value.get("id")
    if isinstance(quantity, int) and currency == "USD":
        return f"${quantity:,}"
    if isinstance(quantity, int) and isinstance(currency, str):
        return f"{quantity:,} {currency}"
    return ""


def current_online_items(items: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Keep active Kaggle entries whose public participation is online-only."""
    collected: list[dict[str, Any]] = []
    for item in items:
        slug = item.get("competitionName")
        title = item.get("title")
        deadline = parse_timestamp(item.get("deadline"))
        if not isinstance(slug, str) or not slug or not isinstance(title, str) or not title or deadline is None:
            continue
        if deadline < now:
            continue

        public_text = " ".join(
            str(item.get(field, "")) for field in ("title", "briefDescription", "hostName")
        ).lower()
        if any(marker in public_text for marker in OFFLINE_MARKERS):
            continue

        collected.append(
            {
                "id": f"kaggle-{item.get('id', slug)}",
                "title": title,
                "status": "active",
                "location": "Online",
                "participation_mode": "online",
                "deadline": item["deadline"],
                "description": item.get("briefDescription") or "",
                "organizer": item.get("hostName") or "",
                "participant_count": item.get("totalTeams"),
                "prize": format_reward(item.get("reward")),
                "categories": item.get("categories") if isinstance(item.get("categories"), list) else [],
                "detail_url": f"https://www.kaggle.com/competitions/{slug}",
                "source_url": SOURCE_URL,
                "raw": item,
            }
        )
    return sorted(collected, key=lambda item: item["deadline"])


@dataclass(slots=True)
class KaggleScrapeResult:
    items: list[dict[str, Any]]
    source_pages: list[str]
    warnings: list[str]
    listing_failed: bool = False


class KaggleScraper:
    """Read Kaggle's anonymous public competition-listing API without credentials."""

    def __init__(self) -> None:
        self._timeout = float(os.getenv("KAGGLE_TIMEOUT", "20"))
        self._user_agent = os.getenv(
            "KAGGLE_USER_AGENT",
            "aichallenge-mcp/0.1 (+https://www.kaggle.com/competitions)",
        )

    async def scrape(self) -> KaggleScrapeResult:
        headers = {"User-Agent": self._user_agent}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers=headers,
                follow_redirects=True,
            ) as client:
                await client.get(SOURCE_URL)
                xsrf_token = client.cookies.get("XSRF-TOKEN")
                if not xsrf_token:
                    raise RuntimeError("Kaggle did not provide an anonymous public listing token")

                api_headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-XSRF-TOKEN": xsrf_token,
                }
                total = await self._total_results(client, api_headers)
                page_count = (total + PAGE_SIZE - 1) // PAGE_SIZE
                if page_count > MAXIMUM_PAGES:
                    raise RuntimeError(
                        f"Kaggle listing has {page_count} pages, exceeding the {MAXIMUM_PAGES}-page safety limit"
                    )

                pages = await asyncio.gather(
                    *(
                        self._page(client, api_headers, offset)
                        for offset in range(0, total, PAGE_SIZE)
                    )
                )
        except Exception as exc:  # noqa: BLE001 - source failures are public result data
            return KaggleScrapeResult(
                items=[],
                source_pages=[],
                warnings=[f"목록 페이지 수집 실패: {SOURCE_URL} ({exc})"],
                listing_failed=True,
            )

        raw_items = [item for page in pages for item in page]
        now = datetime.now(timezone.utc)
        return KaggleScrapeResult(
            items=current_online_items(raw_items, now),
            source_pages=[SOURCE_URL, LIST_API_URL],
            warnings=[],
        )

    async def _total_results(self, client: httpx.AsyncClient, headers: dict[str, str]) -> int:
        response = await client.post(
            LIST_API_URL,
            headers=headers,
            json={"selector": {"pageSize": 1}, "readMask": "totalResults"},
        )
        response.raise_for_status()
        total = response.json().get("totalResults")
        if not isinstance(total, int) or total <= 0:
            raise RuntimeError("Kaggle listing returned an invalid total result count")
        return total

    async def _page(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        offset: int,
    ) -> list[dict[str, Any]]:
        request: dict[str, Any] = {"pageSize": PAGE_SIZE}
        if offset:
            request["pageToken"] = str(offset)
        response = await client.post(LIST_API_URL, headers=headers, json=request)
        response.raise_for_status()
        items = response.json().get("competitions")
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            raise RuntimeError(f"Kaggle listing page at offset {offset} has an invalid item shape")
        return items


class KaggleSourceAdapter:
    """Collect active Kaggle competitions with online-only participation policy."""

    source_id = "kaggle_competitions"
    source_name = "Kaggle Competitions"
    source_url = SOURCE_URL
    required_item_fields = ("id", "title", "status", "location", "detail_url", "source_url")

    def __init__(
        self,
        scraper: KaggleScraper | None = None,
        now: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._scraper = scraper or KaggleScraper()
        self._now = now

    async def collect(self) -> dict[str, Any]:
        checked_at = self._now()
        try:
            result = await self._scraper.scrape()
        except Exception as exc:  # noqa: BLE001 - source failures are public result data
            return self._failure(checked_at, [], [], f"collection failed: {exc}")

        if not isinstance(result, KaggleScrapeResult):
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
                "source contract failed: no active online Kaggle competitions collected",
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
        online_only = all(item.get("location") == "Online" for item in result.items)
        detail_urls_valid = all(self._is_kaggle_url(item.get("detail_url")) for item in result.items)
        if missing_fields or not online_only or not detail_urls_valid:
            detail = ", ".join(missing_fields) if missing_fields else "invalid online item metadata"
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
            source_pages=result.source_pages,
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
    def _is_kaggle_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value)
        return parsed.scheme == "https" and parsed.netloc in {"www.kaggle.com", "kaggle.com"}

    @classmethod
    def _valid_metadata(cls, source_pages: list[str], warnings: list[str]) -> bool:
        return all(cls._is_kaggle_url(page) for page in source_pages) and all(
            isinstance(warning, str) for warning in warnings
        )
