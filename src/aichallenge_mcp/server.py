from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .orchestrator import CollectionOrchestrator
from .service import BriefingService
from .sources.aichallenge4all import Aichallenge4allSourceAdapter
from .sources.registry import SourceRegistration, SourceRegistry


mcp = FastMCP(
    "AI Challenge Briefing",
    instructions=(
        "For every request for an AI competition briefing, today's/latest competitions, new "
        "competitions, changes, 접수중, or 진행중, you MUST call refresh_and_brief before "
        "answering. Do not substitute web search: this server is the authoritative source for "
        "aichallenge4all.or.kr and preserves prior snapshots for comparison. Use "
        "get_active_overview only after refresh_and_brief when the user asks for stored active "
        "items, and use search/fetch only for a known stored competition. Never treat a failed "
        "fetch as a closing. Respond in Korean and retain source URLs from tool results."
    ),
)
_legacy_service: BriefingService | None = None
aichallenge4all_source = Aichallenge4allSourceAdapter()
source_registry = SourceRegistry(
    (
        SourceRegistration(
            adapter=aichallenge4all_source,
            public_tool_name="collect_aichallenge4all",
        ),
    )
)
orchestrator = CollectionOrchestrator(source_registry)


def json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def legacy_service() -> BriefingService:
    """Lazily create the persistence-backed service until legacy tools retire."""
    global _legacy_service
    if _legacy_service is None:
        _legacy_service = BriefingService()
    return _legacy_service


@mcp.tool(
    name="refresh_and_brief",
    annotations=ToolAnnotations(
        title="Refresh AI competition briefing",
        # Snapshot persistence is an internal cache only; the tool does not
        # modify user data or any external service and is safe to invoke.
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def refresh_and_brief() -> str:
    """MUST CALL THIS FIRST for every AI competition briefing request.

    This includes Korean requests such as "오늘 AI 대회 브리핑해줘", "접수중인 대회만",
    and "지난 수집 이후 신규·변경만". Fetch public aichallenge4all.or.kr pages,
    compare them with the previous successful snapshot, and return new, changed, active,
    urgent, source, and warning data as JSON. Do not use general web search instead.
    """
    return json_text(legacy_service().refresh())


@mcp.tool(
    name="collect_aichallenge4all",
    annotations=ToolAnnotations(
        title="Collect AI Challenge for All",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def collect_aichallenge4all() -> str:
    """Collect the current public AI Challenge for All source without stored history.

    Returns the complete source-native items and audit metadata. A zero-item or
    invalid collection is reported as a source failure, never as a closed listing.
    """
    return json_text(await aichallenge4all_source.collect())


@mcp.tool(
    name="collect_all_sources",
    annotations=ToolAnnotations(
        title="Collect all registered sources",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def collect_all_sources() -> str:
    """Collect every registered public source concurrently.

    Returns each source's complete result in a separate section. A failed source
    is retried once and reported without discarding successful source results.
    """
    return json_text(await orchestrator.collect())


@mcp.tool(
    name="get_active_overview",
    annotations=ToolAnnotations(
        title="Get active competition overview",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def get_active_overview(status: str | None = None) -> str:
    """Use this when the user wants stored 접수중 or 진행중 competition status.

    For the newest status, call refresh_and_brief first.
    """
    allowed = {None, "접수중", "진행중"}
    if status not in allowed:
        return json_text({"error": "status must be 접수중, 진행중, or omitted"})
    return json_text(legacy_service().active_overview(status))


@mcp.tool(
    name="search",
    annotations=ToolAnnotations(
        title="Search competition index",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def search(query: str) -> str:
    """Search the stored read-only competition index by title or description."""
    return json_text(
        {
            "results": [
                {"id": item["id"], "title": item["title"], "url": item.get("detail_url") or item.get("registration_url") or item.get("source_url")}
                for item in legacy_service().search(query)
            ]
        }
    )


@mcp.tool(
    name="fetch",
    annotations=ToolAnnotations(
        title="Fetch competition",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
def fetch(item_id: str) -> str:
    """Fetch one competition from the stored read-only index by id."""
    item = legacy_service().fetch(item_id)
    if item is None:
        return json_text({"error": "competition not found", "id": item_id})
    return json_text(
        {
            "id": item["id"],
            "title": item["title"],
            "text": item.get("description", ""),
            "url": item.get("detail_url") or item.get("registration_url") or item.get("source_url"),
            "metadata": item,
        }
    )


def main() -> None:
    # Configure the listener explicitly so local tunnels and hosted deployments
    # can choose their port without relying on SDK-version-specific env parsing.
    mcp.settings.host = os.getenv("MCP_HOST", "0.0.0.0")
    mcp.settings.port = int(os.getenv("MCP_PORT", "8000"))

    # FastMCP protects localhost servers from DNS rebinding by validating Host.
    # A reverse proxy or HTTPS tunnel has a different public Host header, so an
    # operator must explicitly allow that exact hostname at runtime.  Keeping it
    # out of source code prevents accidentally trusting arbitrary hosts.
    allowed_hosts = [
        host.strip()
        for host in os.getenv("MCP_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]
    if allowed_hosts and mcp.settings.transport_security is not None:
        mcp.settings.transport_security.allowed_hosts.extend(allowed_hosts)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
