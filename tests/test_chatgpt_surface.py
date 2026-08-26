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
    assert orchestrator.meta["openai/toolInvocation/invoked"] == "AI 대회 정보 수집을 마쳤습니다."


def test_mcp_is_data_only_and_exposes_no_app_widget_resource():
    from aichallenge_mcp import server

    resources = asyncio.run(server.mcp.list_resources())

    assert resources == []


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


def test_public_asgi_surface_exposes_liveness_readiness_and_mcp_discovery(monkeypatch):
    from aichallenge_mcp import server
    from starlette.testclient import TestClient

    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "testserver")
    app = server.create_app()
    payload = {
        "jsonrpc": "2.0",
        "id": "discover-public-1",
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
        assert client.get("/healthz").json() == {"status": "ok", "service": "aichallenge-mcp"}
        assert client.get("/readyz").json()["status"] == "ready"
        response = client.post("/mcp", json=payload, headers=headers)

    assert response.status_code == 200
    assert response.json()["result"]["resultType"] == "complete"


def test_production_readiness_reports_configuration_gaps_without_secret_values(monkeypatch):
    from aichallenge_mcp import server
    from starlette.testclient import TestClient

    monkeypatch.setenv("MCP_PRODUCTION", "true")
    monkeypatch.setenv("REQUIRE_KAGGLE_CREDENTIALS", "true")
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)

    with TestClient(server.create_app()) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "failures": [
            "MCP_ALLOWED_HOSTS must include the public MCP hostname in production",
            "Kaggle runtime credentials are required but not configured",
        ],
    }


def test_managed_host_port_takes_precedence_over_local_mcp_port(monkeypatch):
    from aichallenge_mcp import server

    monkeypatch.setenv("MCP_PORT", "8000")
    monkeypatch.setenv("PORT", "9000")

    assert server.listening_port() == 9000


def test_chatgpt_skill_calls_only_the_collection_orchestrator():
    skill = (Path(__file__).parents[1] / "chatgpt-skills" / "ai-contest-briefing" / "SKILL.md").read_text()

    assert "collect_all_sources" in skill
    assert "refresh_and_brief" not in skill
    assert "get_active_overview" not in skill
    assert "`search`" not in skill
    assert "`fetch`" not in skill
    assert "aichallenge-mcp.columnar.v1" in skill
    assert "ai-contest-data-YYYY-MM-DD.json" in skill
    assert "exactly `structuredContent.collection`" in skill
    assert "Do not enumerate all competitions in the chat body" in skill
    assert "only when the user explicitly asks" in skill
    assert "## Follow-up conversation" in skill
    assert "**Always write a visible Korean answer**" in skill
    assert "For participation-fit questions or a request to conduct an interview" in skill


def test_distributable_skill_archives_match_the_orchestrator_workflow():
    root = Path(__file__).parents[1] / "chatgpt-skills"

    for archive_name in ("ai-contest-briefing-chatgpt.skill.zip", "ai-contest-briefing.skill.zip"):
        with ZipFile(root / archive_name) as archive:
            skill = archive.read("ai-contest-briefing/SKILL.md").decode()
            manifest = archive.read("ai-contest-briefing/agents/openai.yaml").decode()

        assert "collect_all_sources" in skill
        assert "aichallenge-mcp.columnar.v1" in skill
        assert "ai-contest-data-YYYY-MM-DD.json" in skill
        assert "exactly `structuredContent.collection`" in skill
        assert "only when the user explicitly asks" in skill
        assert "## Follow-up conversation" in skill
        assert "**Always write a visible Korean answer**" in skill
        assert "refresh_and_brief" not in skill
        assert "collect every registered" in manifest
