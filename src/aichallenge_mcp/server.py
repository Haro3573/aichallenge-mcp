from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from typing import Any

import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .briefing_document import compact_collection, compact_summary
from .orchestrator import CollectionOrchestrator
from .sources.aichallenge4all import Aichallenge4allSourceAdapter
from .sources.dacon import DaconSourceAdapter
from .sources.devpost import DevpostSourceAdapter
from .sources.kaggle import KaggleSourceAdapter, resolve_credentials
from .sources.registry import SourceRegistration, SourceRegistry


mcp = MCPServer(
    "AI Challenge Briefing",
    version="0.1.0",
    instructions=(
        "For a current AI competition briefing, you MUST call collect_all_sources before "
        "answering. For that initial briefing turn, call no direct source tool after "
        "collect_all_sources: it returns a compact status summary and complete, lossless columnar "
        "current data in structured content. For the initial briefing, make a concise Korean "
        "summary only; do not create a file or reproduce every competition unless the user later "
        "explicitly requests a complete report. Direct source tools are only for a later, "
        "user-requested source-specific "
        "follow-up. Do not substitute "
        "web search or prior conversation. This server collects "
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


def _env_flag(name: str, *, default: bool = False) -> bool:
    """Read an explicitly configured boolean without accepting ambiguous values."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def allowed_hosts() -> list[str]:
    """Return local hosts plus the operator-declared public MCP host names."""
    return [
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


def listening_port() -> int:
    """Use the managed-hosting PORT contract while retaining local MCP_PORT support."""
    return int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))


def readiness_failures() -> list[str]:
    """Return deployment configuration failures without exposing any secret value."""
    failures: list[str] = []
    if _env_flag("MCP_PRODUCTION") and not os.getenv("MCP_ALLOWED_HOSTS", "").strip():
        failures.append("MCP_ALLOWED_HOSTS must include the public MCP hostname in production")
    if _env_flag("REQUIRE_KAGGLE_CREDENTIALS") and resolve_credentials() is None:
        failures.append("Kaggle runtime credentials are required but not configured")
    return failures


async def healthz(_: Any) -> JSONResponse:
    """Liveness probe: this process can serve HTTP requests."""
    return JSONResponse({"status": "ok", "service": "aichallenge-mcp"})


async def readyz(_: Any) -> JSONResponse:
    """Readiness probe: deployment-critical configuration is present."""
    failures = readiness_failures()
    status_code = 200 if not failures else 503
    return JSONResponse(
        {"status": "ready" if not failures else "not_ready", "failures": failures},
        status_code=status_code,
    )


def create_app() -> Starlette:
    """Create the public ASGI surface for a stateless, horizontally scalable MCP server."""
    mcp_app = mcp.streamable_http_app(
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        stateless_http=_env_flag("MCP_STATELESS_HTTP", default=True),
        transport_security=TransportSecuritySettings(allowed_hosts=allowed_hosts()),
    )

    @asynccontextmanager
    async def lifespan(_: Starlette):
        # Mounted Starlette applications do not run their own lifespan. The MCP
        # transport needs it to initialize its request task group.
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    return Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Route("/readyz", readyz, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        lifespan=lifespan,
    )

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
    meta={
        "openai/toolInvocation/invoking": "AI 대회 정보를 수집하는 중입니다…",
        "openai/toolInvocation/invoked": "AI 대회 정보 수집을 마쳤습니다.",
    },
)
async def collect_all_sources() -> CallToolResult:
    """Collect every registered public source concurrently.

    Returns a compact conversation summary plus complete lossless columnar data
    for the model to present now or turn into a native ChatGPT document only on
    a later explicit full-report request. A failed
    source is retried once and reported without discarding successful results.
    This server is stateless: it cannot compare against conversation context,
    prior runs, snapshots, or any other history. For a history request, do not
    call this tool; use history_comparison.required_response_ko instead.
    """
    collection = await orchestrator.collect()
    summary = compact_summary(collection)
    counts = summary["counts"]
    text = (
        "AI 대회 수집 완료: "
        f"source {counts.get('succeeded', 0)}/{counts.get('total', 0)} 성공, "
        f"항목 {summary['item_count']}건입니다. "
        "전체 정규화 데이터는 structured content에 제공됩니다."
    )
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent={
            "summary": summary,
            "collection": compact_collection(collection),
        },
    )


def main() -> None:
    uvicorn.run(
        create_app(),
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=listening_port(),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
