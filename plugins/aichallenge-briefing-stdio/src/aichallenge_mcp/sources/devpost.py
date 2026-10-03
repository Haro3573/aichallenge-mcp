from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import os
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ..models import utc_now_iso
from .result import source_result


SOURCE_URL = "https://devpost.com/hackathons"
LIST_API_URL = "https://devpost.com/api/hackathons"
PAGE_SIZE = 40
MAXIMUM_PAGES = 20


def clean_html(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def active_devpost_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize active public Devpost hackathons from one API response page."""
    hackathons = payload.get("hackathons")
    if not isinstance(hackathons, list):
        raise ValueError("Devpost listing page has an invalid hackathons shape")

    items: list[dict[str, Any]] = []
    for hackathon in hackathons:
        if (
            not isinstance(hackathon, dict)
            or hackathon.get("open_state") != "open"
            or hackathon.get("invite_only") is True
        ):
            continue

        identifier = hackathon.get("id")
        title = hackathon.get("title")
        detail_url = hackathon.get("url")
        if not isinstance(identifier, int) or not isinstance(title, str) or not title:
            continue
        if not isinstance(detail_url, str) or not detail_url:
            continue

        displayed_location = hackathon.get("displayed_location")
        location = ""
        if isinstance(displayed_location, dict):
            candidate = displayed_location.get("location")
            if isinstance(candidate, str):
                location = candidate
        themes = hackathon.get("themes")
        theme_names = (
            [theme["name"] for theme in themes if isinstance(theme, dict) and isinstance(theme.get("name"), str)]
            if isinstance(themes, list)
            else []
        )

        items.append(
            {
                "id": f"devpost-{identifier}",
                "title": title,
                "status": "open",
                "location": location,
                "submission_period": hackathon.get("submission_period_dates") or "",
                "time_left_to_submission": hackathon.get("time_left_to_submission") or "",
                "themes": theme_names,
                "prize": clean_html(hackathon.get("prize_amount")),
                "organizer": hackathon.get("organization_name") or "",
                "registration_count": hackathon.get("registrations_count"),
                "detail_url": detail_url,
                "source_url": SOURCE_URL,
                "raw": hackathon,
            }
        )
    return items


@dataclass(slots=True)
class DevpostScrapeResult:
    items: list[dict[str, Any]]
    source_pages: list[str]
    warnings: list[str]
    listing_failed: bool = False


class DevpostScraper:
    """Read Devpost's anonymous public list API without credentials."""

    def __init__(self) -> None:
        self._timeout = float(os.getenv("DEVPOST_TIMEOUT", "20"))
        self._user_agent = os.getenv(
            "DEVPOST_USER_AGENT",
            "aichallenge-mcp/0.1 (+https://devpost.com/hackathons)",
        )

    async def scrape(self) -> DevpostScrapeResult:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                follow_redirects=True,
            ) as client:
                first_page = await self._page(client, 1)
                meta = first_page.get("meta")
                if not isinstance(meta, dict):
                    raise RuntimeError("Devpost listing response has invalid metadata")
                total = meta.get("total_count")
                per_page = meta.get("per_page")
                if not isinstance(total, int) or total < 0 or not isinstance(per_page, int) or per_page <= 0:
                    raise RuntimeError("Devpost listing response has invalid pagination metadata")

                page_count = (total + per_page - 1) // per_page
                if page_count > MAXIMUM_PAGES:
                    raise RuntimeError(
                        f"Devpost listing has {page_count} pages, exceeding the {MAXIMUM_PAGES}-page safety limit"
                    )
                remaining_pages = await asyncio.gather(
                    *(self._page(client, page) for page in range(2, page_count + 1))
                )
        except Exception as exc:  # noqa: BLE001 - source failures are public result data
            return DevpostScrapeResult(
                items=[],
                source_pages=[],
                warnings=[f"목록 API 수집 실패: {LIST_API_URL} ({exc})"],
                listing_failed=True,
            )

        try:
            items = [item for page in [first_page, *remaining_pages] for item in active_devpost_items(page)]
        except ValueError as exc:
            return DevpostScrapeResult(
                items=[],
                source_pages=[SOURCE_URL, LIST_API_URL],
                warnings=[f"목록 API 응답 해석 실패: {LIST_API_URL} ({exc})"],
                listing_failed=True,
            )
        return DevpostScrapeResult(
            items=items,
            source_pages=[SOURCE_URL, LIST_API_URL],
            warnings=[],
        )

    @staticmethod
    async def _page(client: httpx.AsyncClient, page: int) -> dict[str, Any]:
        response = await client.get(
            LIST_API_URL,
            params={"status": "open", "page": page, "per_page": PAGE_SIZE},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Devpost listing page {page} has an invalid response shape")
        return payload


class DevpostSourceAdapter:
    """Collect public Devpost hackathons that are currently open for submissions."""

    source_id = "devpost_hackathons"
    source_name = "Devpost Hackathons"
    source_url = SOURCE_URL
    required_item_fields = ("id", "title", "status", "detail_url", "source_url")

    def __init__(
        self,
        scraper: DevpostScraper | None = None,
        now: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._scraper = scraper or DevpostScraper()
        self._now = now

    async def collect(self) -> dict[str, Any]:
        checked_at = self._now()
        try:
            result = await self._scraper.scrape()
        except Exception as exc:  # noqa: BLE001 - source failures are public result data
            return self._failure(checked_at, [], [], f"collection failed: {exc}")

        if not isinstance(result, DevpostScrapeResult):
            return self._failure(checked_at, [], [], "source contract failed: invalid scraper result")
        if result.listing_failed:
            return self._failure(
                checked_at,
                result.source_pages,
                result.warnings,
                "source contract failed: listing API retrieval failed",
            )
        if not self._valid_metadata(result.source_pages, result.warnings):
            return self._failure(checked_at, [], [], "source contract failed: invalid scraper result")
        if not result.items:
            return self._failure(
                checked_at,
                result.source_pages,
                result.warnings,
                "source contract failed: no open Devpost hackathons collected",
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
        all_open = all(item.get("status") == "open" for item in result.items)
        detail_urls_valid = all(self._is_devpost_url(item.get("detail_url")) for item in result.items)
        if missing_fields or not all_open or not detail_urls_valid:
            detail = ", ".join(missing_fields) if missing_fields else "invalid open item metadata"
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
    def _is_devpost_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value)
        return parsed.scheme == "https" and (
            parsed.netloc == "devpost.com" or parsed.netloc.endswith(".devpost.com")
        )

    @classmethod
    def _valid_metadata(cls, source_pages: list[str], warnings: list[str]) -> bool:
        return all(cls._is_devpost_url(page) for page in source_pages) and all(
            isinstance(warning, str) for warning in warnings
        )
