from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import inspect
import os
import re
from typing import Any

from .db import Database
from .models import ACTIVE_STATUSES, Competition, utc_now_iso
from .scraper import ScrapeResult, Scraper


def parse_deadline(raw: str) -> date | None:
    if not raw:
        return None
    text = raw.replace("'", "20").replace("년", ".").replace("월", ".").replace("일", "")
    match = re.search(r"(?:(20\d{2})[.\-/\s]*)?(\d{1,2})[.\-/\s]+(\d{1,2})", text)
    if not match:
        return None
    year = int(match.group(1) or datetime.now().year)
    month = int(match.group(2))
    day = int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


class BriefingService:
    def __init__(self, db: Database | None = None, scraper: Scraper | None = None) -> None:
        self.db = db or Database(os.getenv("AI_CHALLENGE_DB", "./data/aichallenge.sqlite3"))
        self.scraper = scraper or Scraper()

    def refresh(self) -> dict[str, Any]:
        run_id = self.db.start_run()
        try:
            scraped = self.scraper.scrape()
            result: ScrapeResult = asyncio.run(scraped) if inspect.isawaitable(scraped) else scraped
            # A scraper that could not retrieve any seed page returns warnings and
            # no candidates.  Do not present that as a successful empty index: it
            # must preserve the previous snapshot and be visible to the caller.
            if not result.items and result.warnings:
                self.db.finish_run(
                    run_id,
                    status="failed",
                    error="; ".join(result.warnings),
                )
                return {
                    "run_id": run_id,
                    "checked_at": utc_now_iso(),
                    "counts": {},
                    "new_items": [],
                    "changed_items": [],
                    "active_items": self.db.active(),
                    "urgent_items": [],
                    "sources": result.sources,
                    "warnings": ["전체 수집 실패: 이전 수집 결과를 유지합니다.", *result.warnings],
                }
            counts = {"new": 0, "changed": 0, "unchanged": 0}
            for item in result.items:
                counts[self.db.upsert(item, run_id)] += 1
            self.db.finish_run(run_id, status="success", item_count=len(result.items))
            changes = self.db.changes_for_run(run_id)
            active = self.db.active()
            return {
                "run_id": run_id,
                "checked_at": utc_now_iso(),
                "counts": counts,
                "new_items": [c["after"] for c in changes if c["change_type"] == "new"],
                "changed_items": [c for c in changes if c["change_type"] == "changed"],
                "active_items": active,
                "urgent_items": self._urgent(active),
                "sources": result.sources,
                "warnings": result.warnings,
            }
        except Exception as exc:  # noqa: BLE001 - convert run failure into inspectable result
            self.db.finish_run(run_id, status="failed", error=str(exc))
            return {
                "run_id": run_id,
                "checked_at": utc_now_iso(),
                "counts": {},
                "new_items": [],
                "changed_items": [],
                "active_items": self.db.active(),
                "urgent_items": [],
                "sources": [],
                "warnings": [f"전체 수집 실패: {exc}"],
            }

    @staticmethod
    def _urgent(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        today = date.today()
        result: list[dict[str, Any]] = []
        for item in items:
            deadline = parse_deadline(item.get("registration_period", ""))
            if deadline and today <= deadline <= today + timedelta(days=7):
                result.append(item)
        return result

    def active_overview(self, status: str | None = None) -> dict[str, Any]:
        items = self.db.active(status)
        return {"checked_at": utc_now_iso(), "status": status or "접수중·진행중", "items": items}

    def search(self, query: str) -> list[dict[str, Any]]:
        return self.db.search(query)

    def fetch(self, item_id: str) -> dict[str, Any] | None:
        return self.db.fetch(item_id)
