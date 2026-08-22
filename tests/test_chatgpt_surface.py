from __future__ import annotations

import asyncio
from pathlib import Path
from zipfile import ZipFile


def test_mcp_exposes_only_the_orchestrator_and_registered_source_tools():
    from aichallenge_mcp import server

    tools = asyncio.run(server.mcp.list_tools())
    tool_names = {tool.name for tool in tools}

    assert tool_names == {
        "collect_all_sources",
        "collect_aichallenge4all",
        "collect_dacon_competitions",
    }
    assert "stored" not in server.mcp.instructions
    assert "refresh_and_brief" not in server.mcp.instructions
    assert "Never claim" in server.mcp.instructions
    assert "Never compare" in server.mcp.instructions
    assert any("history" in (tool.description or "").lower() for tool in tools)


def test_chatgpt_skill_calls_only_the_collection_orchestrator():
    skill = (Path(__file__).parents[1] / "chatgpt-skills" / "ai-contest-briefing" / "SKILL.md").read_text()

    assert "collect_all_sources" in skill
    assert "refresh_and_brief" not in skill
    assert "get_active_overview" not in skill
    assert "`search`" not in skill
    assert "`fetch`" not in skill


def test_distributable_skill_archives_match_the_orchestrator_workflow():
    root = Path(__file__).parents[1] / "chatgpt-skills"

    for archive_name in ("ai-contest-briefing-chatgpt.skill.zip", "ai-contest-briefing.skill.zip"):
        with ZipFile(root / archive_name) as archive:
            skill = archive.read("ai-contest-briefing/SKILL.md").decode()
            manifest = archive.read("ai-contest-briefing/agents/openai.yaml").decode()

        assert "collect_all_sources" in skill
        assert "refresh_and_brief" not in skill
        assert "collect every registered" in manifest
