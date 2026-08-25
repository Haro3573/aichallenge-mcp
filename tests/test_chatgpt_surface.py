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
        "collect_kaggle_competitions",
        "collect_devpost_hackathons",
    }
    assert "stored" not in server.mcp.instructions
    assert "refresh_and_brief" not in server.mcp.instructions
    assert "Never claim" in server.mcp.instructions
    assert "Never compare" in server.mcp.instructions
    assert "call no direct source tool" in server.mcp.instructions
    assert any("history" in (tool.description or "").lower() for tool in tools)
    orchestrator = next(tool for tool in tools if tool.name == "collect_all_sources")
    assert orchestrator.meta["ui"]["resourceUri"] == "ui://ai-contest-briefing/briefing-document-v2.html"


def test_mcp_exposes_the_orchestrator_download_widget_resource():
    from aichallenge_mcp import server

    resources = asyncio.run(server.mcp.list_resources())
    resource = next(item for item in resources if item.uri == "ui://ai-contest-briefing/briefing-document-v2.html")
    contents = asyncio.run(server.mcp.read_resource(resource.uri))

    assert resource.mime_type == "text/html;profile=mcp-app"
    assert resource.meta["ui"] == {
        "prefersBorder": True,
        "domain": "https://ai-contest-briefing.example",
        "csp": {"connectDomains": [], "resourceDomains": []},
    }
    assert "ui/notifications/tool-result" in contents[0].content
    assert "briefing_document" in contents[0].content
    assert "Markdown 문서 다운로드" in contents[0].content


def test_mcp_v2_serves_native_modern_discovery():
    from aichallenge_mcp.server import mcp
    from mcp.server.transport_security import TransportSecuritySettings
    from starlette.testclient import TestClient

    app = mcp.streamable_http_app(
        host="127.0.0.1",
        transport_security=TransportSecuritySettings(allowed_hosts=["testserver"]),
    )
    payload = {
        "jsonrpc": "2.0",
        "id": "discover-1",
        "method": "server/discover",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        },
    }
    headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
        "MCP-Method": "server/discover",
    }

    with TestClient(app) as client:
        response = client.post("/mcp", json=payload, headers=headers)

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == ["2026-07-28"]
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "AI Challenge Briefing"


def test_chatgpt_skill_calls_only_the_collection_orchestrator():
    skill = (Path(__file__).parents[1] / "chatgpt-skills" / "ai-contest-briefing" / "SKILL.md").read_text()

    assert "collect_all_sources" in skill
    assert "refresh_and_brief" not in skill
    assert "get_active_overview" not in skill
    assert "`search`" not in skill
    assert "`fetch`" not in skill
    assert "Markdown 문서 다운로드" in skill


def test_distributable_skill_archives_match_the_orchestrator_workflow():
    root = Path(__file__).parents[1] / "chatgpt-skills"

    for archive_name in ("ai-contest-briefing-chatgpt.skill.zip", "ai-contest-briefing.skill.zip"):
        with ZipFile(root / archive_name) as archive:
            skill = archive.read("ai-contest-briefing/SKILL.md").decode()
            manifest = archive.read("ai-contest-briefing/agents/openai.yaml").decode()

        assert "collect_all_sources" in skill
        assert "Markdown 문서 다운로드" in skill
        assert "refresh_and_brief" not in skill
        assert "collect every registered" in manifest
