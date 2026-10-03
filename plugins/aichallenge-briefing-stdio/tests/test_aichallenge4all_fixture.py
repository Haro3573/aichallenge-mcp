from pathlib import Path

from bs4 import BeautifulSoup

from aichallenge_mcp.scraper import extract_detail_fields


def test_aichallenge4all_detail_fixture_extracts_the_declared_fields():
    fixture = Path(__file__).parent / "fixtures" / "aichallenge4all" / "detail.html"

    fields = extract_detail_fields(BeautifulSoup(fixture.read_text(), "html.parser"))

    assert fields == {
        "schedule": "2026. 9. 1. ~ 2026. 9. 30.",
        "registration_period": "2026. 8. 1. ~ 2026. 8. 20.",
        "contact": "contest@example.org",
        "organizer": "AI Challenge Center",
    }
