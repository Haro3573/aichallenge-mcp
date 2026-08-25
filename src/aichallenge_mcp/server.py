from __future__ import annotations

import json
import os
from typing import Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from .orchestrator import CollectionOrchestrator
from .sources.aichallenge4all import Aichallenge4allSourceAdapter
from .sources.dacon import DaconSourceAdapter
from .sources.devpost import DevpostSourceAdapter
from .sources.kaggle import KaggleSourceAdapter
from .sources.registry import SourceRegistration, SourceRegistry


mcp = MCPServer(
    "AI Challenge Briefing",
    version="0.1.0",
    instructions=(
        "For a current AI competition briefing, you MUST call collect_all_sources before "
        "answering. Do not substitute web search or prior conversation. This server collects "
        "only its operator-registered public sources and returns fresh, source-separated data. "
        "It is stateless: it stores no prior runs, snapshots, or change history. Never compare "
        "results against this conversation, prior conversations, memory, or any other data. "
        "Never claim that results were compared with a previous collection, and never report "
        "newly added, changed, unchanged, or removed competitions. When asked for a comparison, "
        "reply exactly: '이 MCP 서버는 무상태이므로 이전 수집과의 신규·변경·동일·삭제 "
        "비교 결과를 제공할 수 없습니다. 현재 수집 결과만 안내할 수 있습니다.' Do not call "
        "a tool or offer a comparison conclusion. You may offer a new current-only collection instead. "
        "Use a direct collect_<source_id> tool only when a later question needs that one "
        "source's full native result. Never infer that a competition is closed or absent from a "
        "source failure. Respond in Korean and retain original source URLs."
    ),
)
aichallenge4all_source = Aichallenge4allSourceAdapter()
dacon_source = DaconSourceAdapter()
kaggle_source = KaggleSourceAdapter()
devpost_source = DevpostSourceAdapter()
source_registry = SourceRegistry(
    (
        SourceRegistration(
            adapter=aichallenge4all_source,
            public_tool_name="collect_aichallenge4all",
        ),
        SourceRegistration(
            adapter=dacon_source,
            public_tool_name="collect_dacon_competitions",
        ),
        SourceRegistration(
            adapter=kaggle_source,
            public_tool_name="collect_kaggle_competitions",
        ),
        SourceRegistration(
            adapter=devpost_source,
            public_tool_name="collect_devpost_hackathons",
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
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def collect_aichallenge4all() -> str:
    """Collect the current public AI Challenge for All source without stored history.

    Returns the complete source-native items and audit metadata. A zero-item or
    invalid collection is reported as a source failure, never as a closed listing.
    """
    return json_text(await aichallenge4all_source.collect())


@mcp.tool(
    name="collect_dacon_competitions",
    annotations=ToolAnnotations(
        title="Collect active DACON competitions",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def collect_dacon_competitions() -> str:
    """Collect current public, actionable DACON competition entries.

    Returns list-card fields plus optional public detail enrichment. Only
    참가신청중, 진행중, and 연습 entries are included; a listing failure is never
    interpreted as a closed or empty DACON catalogue.
    """
    return json_text(await dacon_source.collect())


@mcp.tool(
    name="collect_kaggle_competitions",
    annotations=ToolAnnotations(
        title="Collect active online Kaggle competitions",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def collect_kaggle_competitions() -> str:
    """Collect active Kaggle competitions with Online location only.

    The source uses Kaggle's official authenticated API. It requires the runtime
    environment to provide KAGGLE_API_TOKEN, or both KAGGLE_USERNAME and
    KAGGLE_KEY; credentials are never returned. Entries whose public metadata
    signals in-person or offline participation are excluded.
    """
    return json_text(await kaggle_source.collect())


@mcp.tool(
    name="collect_devpost_hackathons",
    annotations=ToolAnnotations(
        title="Collect open Devpost hackathons",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def collect_devpost_hackathons() -> str:
    """Collect current public Devpost hackathons open for submissions.

    The source uses Devpost's anonymous public listing API, includes all listed
    participation locations as source-native data, and requires no account or API key.
    """
    return json_text(await devpost_source.collect())


@mcp.tool(
    name="collect_all_sources",
    annotations=ToolAnnotations(
        title="Collect all registered sources",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def collect_all_sources() -> str:
    """Collect every registered public source concurrently.

    Returns each source's complete result in a separate section. A failed source
    is retried once and reported without discarding successful source results.
    This server is stateless: it cannot compare against conversation context,
    prior runs, snapshots, or any other history. For a history request, do not
    call this tool; use history_comparison.required_response_ko instead.
    """
    return json_text(await orchestrator.collect())


def main() -> None:
    # MCP SDK protects localhost servers from DNS rebinding by validating Host.
    # A reverse proxy or HTTPS tunnel has a different public Host header, so an
    # operator may explicitly allow any additional hostname at runtime. The
    # loopback forms are needed by the local Secure MCP Tunnel target.
    allowed_hosts = [
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
        "[::1]",
        "[::1]:*",
    ] + [
        host.strip()
        for host in os.getenv("MCP_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]
    mcp.run(
        transport="streamable-http",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8000")),
        transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts),
    )


if __name__ == "__main__":
    main()
