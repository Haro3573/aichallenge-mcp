from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .orchestrator import CollectionOrchestrator
from .sources.aichallenge4all import Aichallenge4allSourceAdapter
from .sources.registry import SourceRegistration, SourceRegistry


mcp = FastMCP(
    "AI Challenge Briefing",
    instructions=(
        "For a current AI competition briefing, you MUST call collect_all_sources before "
        "answering. Do not substitute web search or prior conversation. This server collects "
        "only its operator-registered public sources and returns fresh, source-separated data. "
        "Use a direct collect_<source_id> tool only when a later question needs that one "
        "source's full native result. Never infer that a competition is closed or absent from a "
        "source failure. Respond in Korean and retain original source URLs."
    ),
)
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
