from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Protocol
from urllib.parse import urlparse

from ..models import utc_now_iso
from .result import source_result


SOURCE_URL = "https://www.kaggle.com/competitions"
LIST_API_URL = "https://api.kaggle.com/v1/competitions.CompetitionApiService/ListCompetitions"
PAGE_SIZE = 100
MAXIMUM_PAGES = 20
OFFLINE_MARKERS = ("in-person", "in person", "on-site", "onsite", "offline")


@dataclass(frozen=True, slots=True)
class KaggleCredentials:
    """Non-persistent runtime credentials for Kaggle's official API client."""

    api_token: str | None = None
    username: str | None = None
    key: str | None = None

    @property
    def method(self) -> str:
        return "access-token" if self.api_token else "legacy-api-key"


class KaggleCompetitionApi(Protocol):
    def list_competitions(self, request: object) -> object: ...


class KaggleCompetitionNamespace(Protocol):
    competition_api_client: KaggleCompetitionApi


class KaggleApiClient(Protocol):
    competitions: KaggleCompetitionNamespace

    def __enter__(self) -> KaggleApiClient: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...


def resolve_credentials(environ: Mapping[str, str] | None = None) -> KaggleCredentials | None:
    """Use explicit runtime environment variables; never read or persist credentials."""
    environment = environ if environ is not None else os.environ
    api_token = environment.get("KAGGLE_API_TOKEN")
    if api_token:
        return KaggleCredentials(api_token=api_token)

    username = environment.get("KAGGLE_USERNAME")
    key = environment.get("KAGGLE_KEY")
    if username and key:
        return KaggleCredentials(username=username, key=key)
    return None


def parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def timestamp_text(value: Any) -> str | None:
    parsed = parse_timestamp(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


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


def _field(value: Any, name: str, *alternate_names: str) -> Any:
    names = (name, *alternate_names)
    if isinstance(value, Mapping):
        for candidate in names:
            if candidate in value:
                return value[candidate]
        return None
    for candidate in names:
        if hasattr(value, candidate):
            return getattr(value, candidate)
    return None


def _tag_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for tag in value:
        name = _field(tag, "name", "full_path", "fullPath", "ref")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return names


def _competition_url(value: Any) -> str | None:
    for candidate in (_field(value, "url"), _field(value, "ref")):
        if not isinstance(candidate, str):
            continue
        parsed = urlparse(candidate)
        if parsed.scheme == "https" and parsed.netloc in {"www.kaggle.com", "kaggle.com"}:
            return candidate
    return None


def _competition_slug(detail_url: str) -> str | None:
    path_parts = [part for part in urlparse(detail_url).path.split("/") if part]
    try:
        index = path_parts.index("competitions")
    except ValueError:
        return None
    return path_parts[index + 1] if index + 1 < len(path_parts) else None


def current_online_items(items: list[Any], now: datetime) -> list[dict[str, Any]]:
    """Convert public API fields to active records under the established online policy.

    Kaggle's list response has no first-class location field. The source keeps its
    existing Online-only contract by excluding an entry only when its public title,
    description, organizer, or category explicitly signals offline participation.
    """
    collected: list[dict[str, Any]] = []
    for item in items:
        detail_url = _competition_url(item)
        title = _field(item, "title")
        deadline = parse_timestamp(_field(item, "deadline"))
        if not detail_url or not isinstance(title, str) or not title or deadline is None:
            continue
        if deadline < now:
            continue

        organizer = _field(item, "organization_name", "organizationName", "host_name", "hostName")
        description = _field(item, "description")
        category = _field(item, "category")
        categories = [category] if isinstance(category, str) and category else []
        for tag in _tag_names(_field(item, "tags")):
            if tag not in categories:
                categories.append(tag)

        public_text = " ".join(
            value.lower()
            for value in (title, description, organizer, *categories)
            if isinstance(value, str)
        )
        if any(marker in public_text for marker in OFFLINE_MARKERS):
            continue

        competition_id = _field(item, "id")
        slug = _competition_slug(detail_url)
        if not isinstance(competition_id, int) and not slug:
            continue

        collected.append(
            {
                "id": f"kaggle-{competition_id if isinstance(competition_id, int) else slug}",
                "title": title,
                "status": "active",
                "location": "Online",
                "participation_mode": "online",
                "deadline": timestamp_text(_field(item, "deadline")),
                "description": description if isinstance(description, str) else "",
                "organizer": organizer if isinstance(organizer, str) else "",
                "participant_count": _field(item, "team_count", "teamCount"),
                "prize": format_reward(_field(item, "reward")),
                "categories": categories,
                "detail_url": detail_url,
                "source_url": SOURCE_URL,
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
    """Collect Kaggle's public competition catalogue via its authenticated API."""

    def __init__(
        self,
        environ: Mapping[str, str] | None = None,
        client_factory: Callable[..., KaggleApiClient] | None = None,
    ) -> None:
        self._environ = environ
        self._client_factory = client_factory

    async def scrape(self) -> KaggleScrapeResult:
        credentials = resolve_credentials(self._environ)
        if credentials is None:
            return KaggleScrapeResult(
                items=[],
                source_pages=[SOURCE_URL],
                warnings=[
                    "Kaggle API 자격증명이 설정되지 않았습니다. "
                    "KAGGLE_API_TOKEN 또는 KAGGLE_USERNAME과 KAGGLE_KEY를 런타임 환경에 설정하세요."
                ],
                listing_failed=True,
            )

        try:
            raw_items = await asyncio.to_thread(self._list_competitions, credentials)
        except Exception as exc:  # noqa: BLE001 - source failures are public result data
            return KaggleScrapeResult(
                items=[],
                source_pages=[SOURCE_URL, LIST_API_URL],
                warnings=[f"Kaggle API 목록 수집 실패: {type(exc).__name__}"],
                listing_failed=True,
            )

        return KaggleScrapeResult(
            items=current_online_items(raw_items, datetime.now(timezone.utc)),
            source_pages=[SOURCE_URL, LIST_API_URL],
            warnings=[],
        )

    def _list_competitions(self, credentials: KaggleCredentials) -> list[Any]:
        from kagglesdk import KaggleClient
        from kagglesdk.competitions.types.competition_api_service import ApiListCompetitionsRequest
        from kagglesdk.competitions.types.competition_enums import (
            CompetitionListTab,
            CompetitionSortBy,
        )

        client_factory = self._client_factory or KaggleClient
        client_kwargs: dict[str, Any] = {
            "user_agent": "aichallenge-mcp/0.1 (+https://www.kaggle.com/competitions)",
        }
        if credentials.api_token:
            client_kwargs["api_token"] = credentials.api_token
        else:
            client_kwargs["username"] = credentials.username
            client_kwargs["password"] = credentials.key

        all_items: list[Any] = []
        seen_tokens: set[str] = set()
        page_token: str | None = None
        with client_factory(**client_kwargs) as client:
            for _ in range(MAXIMUM_PAGES):
                request = ApiListCompetitionsRequest()
                request.group = CompetitionListTab.COMPETITION_LIST_TAB_EVERYTHING
                request.sort_by = CompetitionSortBy.COMPETITION_SORT_BY_LATEST_DEADLINE
                request.page_size = PAGE_SIZE
                if page_token:
                    request.page_token = page_token
                response = client.competitions.competition_api_client.list_competitions(request)
                competitions = _field(response, "competitions")
                if not isinstance(competitions, list):
                    raise RuntimeError("Kaggle API returned an invalid competition list")
                all_items.extend(competitions)

                next_page_token = _field(response, "next_page_token", "nextPageToken")
                if not isinstance(next_page_token, str) or not next_page_token:
                    return all_items
                if next_page_token in seen_tokens:
                    raise RuntimeError("Kaggle API repeated a pagination token")
                seen_tokens.add(next_page_token)
                page_token = next_page_token

        raise RuntimeError(f"Kaggle API exceeded the {MAXIMUM_PAGES}-page safety limit")


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
        return all(cls._is_kaggle_url(page) or page == LIST_API_URL for page in source_pages) and all(
            isinstance(warning, str) for warning in warnings
        )
