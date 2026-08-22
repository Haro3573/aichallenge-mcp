from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .models import Competition, stable_id


BASE_URL = "https://aichallenge4all.or.kr"
SEED_PATHS = ("/university", "/moduai", "/expert")
STATUS_RE = re.compile(r"(접수중|진행중|준비중|참가 마감|마감)")
PRIZE_RE = re.compile(
    r"총\s*상금\s*.*?(?=(?:참가\s*접수중|진행중|준비중|참가\s*마감|마감)|$)"
)


@dataclass(slots=True)
class ScrapeResult:
    items: list[Competition]
    sources: list[str]
    warnings: list[str]


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip("/")


def is_internal_detail(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in {"", "aichallenge4all.or.kr", "www.aichallenge4all.or.kr"} and "/competitions/" in parsed.path


def infer_status(text: str) -> str:
    match = STATUS_RE.search(text)
    if not match:
        return "확인 필요"
    status = match.group(1)
    return "마감" if status == "참가 마감" else status


def infer_title(text: str, preferred: str = "") -> str:
    if preferred:
        return preferred
    text = clean(text)
    text = STATUS_RE.sub("", text)
    text = PRIZE_RE.sub("", text)
    # The track pages often prefix the title with an audience label.
    pieces = re.split(r"\s{2,}|\s+(?=AI\s)|\s+(?=2026\s)|\s+(?=제\d+회)", text, maxsplit=1)
    return clean(pieces[-1] if pieces else text) or "제목 확인 필요"


def infer_audience(text: str, title: str = "") -> str:
    text = clean(text)
    title = title or infer_title(text)
    if title and title in text:
        return clean(text.split(title, 1)[0])
    return ""


def extract_detail_fields(soup: BeautifulSoup) -> dict[str, str]:
    page_text = clean(soup.get_text(" ", strip=True))

    def after_label(labels: Iterable[str], stops: Iterable[str]) -> str:
        for label in labels:
            stop_pattern = "|".join(re.escape(stop) for stop in stops)
            match = re.search(
                re.escape(label) + r"\s*(.*?)(?=" + stop_pattern + r"|$)",
                page_text,
                re.I,
            )
            if match:
                return clean(match.group(1))
        return ""

    return {
        "schedule": after_label(("대회일정", "일정"), ("접수기간", "첨부파일", "문의", "주최")),
        "registration_period": after_label(("접수기간", "접수 기간"), ("권역별 참가 신청", "첨부파일", "문의", "주최")),
        "contact": after_label(("문의", "문의처"), ("주최", "주관", "개인정보")),
        "organizer": after_label(("주최·주관", "주최/주관"), ("개인정보", "주관")),
    }


class Scraper:
    def __init__(self) -> None:
        self.timeout = float(os.getenv("AI_CHALLENGE_TIMEOUT", "20"))
        self.user_agent = os.getenv(
            "AI_CHALLENGE_USER_AGENT",
            "aichallenge-mcp/0.1 (+https://aichallenge4all.or.kr/)",
        )

    def fetch_html(self, client: httpx.Client, url: str) -> str:
        response = client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text

    def scrape(self) -> ScrapeResult:
        sources: list[str] = []
        warnings: list[str] = []
        candidates: dict[str, Competition] = {}

        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout, headers=headers) as client:
            for path in SEED_PATHS:
                url = urljoin(BASE_URL, path)
                try:
                    html = self.fetch_html(client, url)
                    sources.append(url)
                    soup = BeautifulSoup(html, "html.parser")
                    for anchor in soup.select("a[href]"):
                        href = canonical_url(urljoin(url, anchor.get("href", "")))
                        text = clean(anchor.get_text(" ", strip=True))
                        if not text or not STATUS_RE.search(text):
                            continue
                        if href in {canonical_url(BASE_URL), canonical_url(url)}:
                            continue
                        card_title = clean(anchor.find("img").get("alt", "")) if anchor.find("img") else ""
                        title = infer_title(text, card_title)
                        item = Competition(
                            id=stable_id(href, title),
                            title=title,
                            status=infer_status(text),
                            audience=infer_audience(text, title),
                            description=text,
                            prize=clean(PRIZE_RE.search(text).group(0)) if PRIZE_RE.search(text) else "",
                            registration_url=href if not is_internal_detail(href) else "",
                            detail_url=href if is_internal_detail(href) else "",
                            source_url=url,
                            raw_text=text,
                        )
                        existing = candidates.get(item.id)
                        if existing is None or len(item.description) > len(existing.description):
                            candidates[item.id] = item
                except Exception as exc:  # noqa: BLE001 - keep collecting other seed pages
                    warnings.append(f"목록 페이지 수집 실패: {url} ({exc})")

            # Enrich internal detail pages. Failures do not erase the list item.
            for item in list(candidates.values()):
                if not item.detail_url:
                    continue
                try:
                    html = self.fetch_html(client, item.detail_url)
                    detail = extract_detail_fields(BeautifulSoup(html, "html.parser"))
                    item.schedule = detail["schedule"]
                    item.registration_period = detail["registration_period"]
                    item.contact = detail["contact"]
                    item.organizer = detail["organizer"]
                    sources.append(item.detail_url)
                except Exception as exc:  # noqa: BLE001 - one bad page must not stop the run
                    warnings.append(f"상세 페이지 수집 실패: {item.detail_url} ({exc})")

        return ScrapeResult(list(candidates.values()), sorted(set(sources)), warnings)
