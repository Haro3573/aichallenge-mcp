from aichallenge_mcp.models import Competition, stable_id
from aichallenge_mcp.db import Database
from aichallenge_mcp.scraper import ScrapeResult
from aichallenge_mcp.service import BriefingService


def test_competition_fingerprint_ignores_id_only():
    first = Competition(id="one", title="대회", status="접수중")
    second = Competition(id="two", title="대회", status="접수중")
    assert first.fingerprint() == second.fingerprint()


def test_stable_id_is_repeatable():
    assert stable_id("https://example.com/a", "대회") == stable_id("https://example.com/a", "대회")


def test_empty_scrape_with_warnings_is_marked_failed_and_keeps_previous_data(tmp_path):
    class EmptyScraper:
        def scrape(self):
            return ScrapeResult(items=[], sources=[], warnings=["목록 페이지 수집 실패"])

    service = BriefingService(
        db=Database(str(tmp_path / "competitions.sqlite3")),
        scraper=EmptyScraper(),
    )

    result = service.refresh()

    assert result["counts"] == {}
    assert result["active_items"] == []
    assert result["warnings"][0] == "전체 수집 실패: 이전 수집 결과를 유지합니다."
    with service.db.connect() as connection:
        assert connection.execute("SELECT status FROM runs").fetchone()["status"] == "failed"
