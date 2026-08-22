from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


ACTIVE_STATUSES = {"접수중", "진행중"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Competition:
    id: str
    title: str
    status: str
    audience: str = ""
    description: str = ""
    schedule: str = ""
    registration_period: str = ""
    prize: str = ""
    organizer: str = ""
    registration_url: str = ""
    detail_url: str = ""
    source_url: str = ""
    contact: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fingerprint(self) -> str:
        payload = self.to_dict().copy()
        payload.pop("id", None)
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_id(url: str, title: str) -> str:
    value = url.strip() or title.strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
