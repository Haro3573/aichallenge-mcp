from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .models import utc_now_iso
from .sources.registry import SourceRegistration, SourceRegistry
from .sources.result import source_result


class CollectionOrchestrator:
    """Run every registered source adapter concurrently for one collection run."""

    def __init__(
        self,
        source_registry: SourceRegistry,
        *,
        timeout_seconds: float = 20,
        retries: int = 1,
        now: Callable[[], str] = utc_now_iso,
    ) -> None:
        self._source_registry = source_registry
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._now = now

    async def collect(self) -> dict[str, Any]:
        checked_at = self._now()
        sources = await asyncio.gather(
            *(
                self._collect_registration(registration, checked_at)
                for registration in self._source_registry.registrations
            )
        )
        succeeded = sum(source["success"] for source in sources)
        return {
            "checked_at": checked_at,
            "counts": {
                "total": len(sources),
                "succeeded": succeeded,
                "failed": len(sources) - succeeded,
            },
            "sources": sources,
        }

    async def _collect_registration(
        self,
        registration: SourceRegistration,
        checked_at: str,
    ) -> dict[str, Any]:
        attempts = self._retries + 1
        last_result: dict[str, Any] | None = None

        for attempt in range(1, attempts + 1):
            try:
                result = await asyncio.wait_for(registration.adapter.collect(), timeout=self._timeout_seconds)
            except TimeoutError:
                last_result = self._failure(
                    registration,
                    checked_at,
                    f"collection timed out after {attempt} attempts",
                )
            except Exception as exc:  # noqa: BLE001 - a source error must not halt its peers
                last_result = self._failure(
                    registration,
                    checked_at,
                    f"collection failed after {attempt} attempts: {exc}",
                )
            else:
                if not self._valid_source_result(result, registration):
                    last_result = self._failure(
                        registration,
                        checked_at,
                        f"source returned invalid collection result after {attempt} attempts",
                    )
                elif result["success"]:
                    return {**result, "attempts": attempt}
                else:
                    last_result = {**result, "attempts": attempt}

        assert last_result is not None
        return {**last_result, "attempts": attempts}

    @staticmethod
    def _valid_source_result(result: Any, registration: SourceRegistration) -> bool:
        return (
            isinstance(result, dict)
            and result.get("source_id") == registration.adapter.source_id
            and result.get("source_name") == registration.adapter.source_name
            and result.get("source_url") == registration.adapter.source_url
            and CollectionOrchestrator._valid_checked_at(result.get("checked_at"))
            and isinstance(result.get("success"), bool)
            and isinstance(result.get("items"), list)
            and isinstance(result.get("source_pages"), list)
            and isinstance(result.get("warnings"), list)
            and (
                (result["success"] and result.get("error") is None)
                or (not result["success"] and isinstance(result.get("error"), str) and bool(result["error"]))
            )
        )

    @staticmethod
    def _valid_checked_at(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return True

    @staticmethod
    def _failure(
        registration: SourceRegistration,
        checked_at: str,
        error: str,
    ) -> dict[str, Any]:
        adapter = registration.adapter
        return source_result(
            source_id=adapter.source_id,
            source_name=adapter.source_name,
            source_url=adapter.source_url,
            checked_at=checked_at,
            success=False,
            items=[],
            source_pages=[],
            warnings=[],
            error=error,
        )
