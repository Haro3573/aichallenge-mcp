from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import urlparse

from ..models import utc_now_iso
from ..scraper import BASE_URL, Scraper
from .result import source_result


class ScraperProtocol(Protocol):
    def scrape(self) -> Awaitable[Any]: ...


class Aichallenge4allSourceAdapter:
    """Collect the current public aichallenge4all competition listing."""

    source_id = "aichallenge4all"
    source_name = "AI Challenge for All"
    source_url = BASE_URL
    required_item_fields = ("id", "title", "status", "source_url")

    def __init__(
        self,
        scraper: ScraperProtocol | None = None,
        now: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._scraper = scraper or Scraper()
        self._now = now

    async def collect(self) -> dict[str, Any]:
        checked_at = self._now()
        try:
            result = await self._scraper.scrape()
        except Exception as exc:  # noqa: BLE001 - source failures are public result data
            return self._failure(checked_at, [], [], f"collection failed: {exc}")

        try:
            items = [item.to_dict() for item in result.items]
            source_pages = list(result.sources)
            warnings = list(result.warnings)
            failed_listing_pages = list(result.failed_listing_pages)
        except Exception:  # noqa: BLE001 - malformed scraper output is source failure data
            return self._failure(
                checked_at,
                [],
                [],
                "source contract failed: invalid scraper result",
            )

        if not self._valid_metadata(source_pages, warnings, failed_listing_pages):
            return self._failure(
                checked_at,
                [],
                [],
                "source contract failed: invalid scraper result",
            )

        if failed_listing_pages:
            return self._failure(
                checked_at,
                source_pages,
                warnings,
                "source contract failed: listing page retrieval failed",
            )

        if not all(isinstance(item, dict) for item in items):
            return self._failure(
                checked_at,
                source_pages,
                warnings,
                "source contract failed: invalid item shape",
            )

        if not items:
            return self._failure(
                checked_at,
                source_pages,
                warnings,
                "source contract failed: no valid items collected",
            )

        missing_fields = sorted(
            {
                field
                for item in items
                for field in self.required_item_fields
                if not item.get(field)
            }
        )
        if missing_fields:
            return self._failure(
                checked_at,
                source_pages,
                warnings,
                f"source contract failed: required fields missing: {', '.join(missing_fields)}",
            )

        if not all(self._is_public_url(item["source_url"]) for item in items):
            return self._failure(
                checked_at,
                source_pages,
                warnings,
                "source contract failed: invalid item source URL",
            )

        return source_result(
            source_id=self.source_id,
            source_name=self.source_name,
            source_url=self.source_url,
            checked_at=checked_at,
            success=True,
            items=items,
            source_pages=source_pages,
            warnings=warnings,
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
    def _valid_metadata(
        source_pages: list[str],
        warnings: list[str],
        failed_listing_pages: list[str],
    ) -> bool:
        return all(Aichallenge4allSourceAdapter._is_public_url(page) for page in source_pages) and all(
            isinstance(warning, str) for warning in warnings
        ) and all(Aichallenge4allSourceAdapter._is_public_url(page) for page in failed_listing_pages)

    @staticmethod
    def _is_public_url(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
