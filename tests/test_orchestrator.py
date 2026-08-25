from __future__ import annotations

import asyncio
import threading

import pytest

from aichallenge_mcp.orchestrator import CollectionOrchestrator
from aichallenge_mcp.sources.registry import SourceRegistration, SourceRegistry


def source_result(source_id: str, *, success: bool = True) -> dict:
    return {
        "source_id": source_id,
        "source_name": f"{source_id} source",
        "source_url": f"https://{source_id}.example.test",
        "checked_at": "2026-08-22T06:00:00+00:00",
        "success": success,
        "items": [{"title": f"{source_id} item"}] if success else [],
        "source_pages": [f"https://{source_id}.example.test/list"],
        "warnings": [],
        "error": None if success else "source contract failed",
    }


class StubAdapter:
    def __init__(self, source_id: str, outcomes: list[dict | Exception]) -> None:
        self.source_id = source_id
        self.source_name = f"{source_id} source"
        self.source_url = f"https://{source_id}.example.test"
        self.outcomes = outcomes
        self.calls = 0

    async def collect(self) -> dict:
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def registration(adapter: StubAdapter) -> SourceRegistration:
    return SourceRegistration(adapter=adapter, public_tool_name=f"collect_{adapter.source_id}")


def test_registry_rejects_duplicate_source_ids():
    first = StubAdapter("one", [source_result("one")])
    duplicate = StubAdapter("one", [source_result("one")])

    with pytest.raises(ValueError, match="duplicate source_id: one"):
        SourceRegistry((registration(first), registration(duplicate)))


def test_orchestrator_starts_registered_sources_concurrently():
    barrier = threading.Barrier(2)

    class BarrierAdapter(StubAdapter):
        async def collect(self) -> dict:
            await asyncio.to_thread(barrier.wait, 0.2)
            return await super().collect()

    first = BarrierAdapter("first", [source_result("first")])
    second = BarrierAdapter("second", [source_result("second")])
    orchestrator = CollectionOrchestrator(
        SourceRegistry((registration(first), registration(second))),
        timeout_seconds=0.5,
        retries=0,
        now=lambda: "2026-08-22T06:00:00+00:00",
    )

    result = asyncio.run(orchestrator.collect())

    assert result["counts"] == {"total": 2, "succeeded": 2, "failed": 0}
    assert [source["source_id"] for source in result["sources"]] == ["first", "second"]


def test_orchestrator_retries_a_failed_source_once_before_reporting_success():
    adapter = StubAdapter(
        "flaky",
        [source_result("flaky", success=False), source_result("flaky", success=True)],
    )
    orchestrator = CollectionOrchestrator(
        SourceRegistry((registration(adapter),)),
        retries=1,
        now=lambda: "2026-08-22T06:00:00+00:00",
    )

    result = asyncio.run(orchestrator.collect())

    assert adapter.calls == 2
    assert result["counts"] == {"total": 1, "succeeded": 1, "failed": 0}
    assert result["sources"][0]["attempts"] == 2
    assert result["sources"][0]["success"] is True


def test_orchestrator_keeps_successful_sources_when_another_source_fails():
    good = StubAdapter("good", [source_result("good")])
    broken = StubAdapter("broken", [RuntimeError("offline")])
    orchestrator = CollectionOrchestrator(
        SourceRegistry((registration(good), registration(broken))),
        retries=1,
        now=lambda: "2026-08-22T06:00:00+00:00",
    )

    result = asyncio.run(orchestrator.collect())

    assert result["counts"] == {"total": 2, "succeeded": 1, "failed": 1}
    assert result["sources"][0]["items"] == [{"title": "good item"}]
    assert result["sources"][1]["success"] is False
    assert result["sources"][1]["error"] == "collection failed after 2 attempts: offline"


def test_orchestrator_reports_a_timeout_after_one_retry():
    class SlowAdapter(StubAdapter):
        async def collect(self) -> dict:
            await asyncio.sleep(0.05)
            return await super().collect()

    slow = SlowAdapter("slow", [source_result("slow")])
    orchestrator = CollectionOrchestrator(
        SourceRegistry((registration(slow),)),
        timeout_seconds=0.01,
        retries=1,
        now=lambda: "2026-08-22T06:00:00+00:00",
    )

    result = asyncio.run(orchestrator.collect())

    assert result["counts"] == {"total": 1, "succeeded": 0, "failed": 1}
    assert result["sources"][0]["attempts"] == 2
    assert result["sources"][0]["error"] == "collection timed out after 2 attempts"


def test_orchestrator_normalizes_a_malformed_failure_without_erasing_peers():
    good = StubAdapter("good", [source_result("good")])
    malformed = StubAdapter(
        "malformed",
        [
            {
                "source_id": "malformed",
                "success": False,
                "items": [],
                "warnings": [],
                "error": None,
            }
        ],
    )
    orchestrator = CollectionOrchestrator(
        SourceRegistry((registration(good), registration(malformed))),
        retries=0,
        now=lambda: "2026-08-22T06:00:00+00:00",
    )

    result = asyncio.run(orchestrator.collect())

    assert result["counts"] == {"total": 2, "succeeded": 1, "failed": 1}
    assert result["sources"][0]["success"] is True
    assert result["sources"][1]["success"] is False
    assert result["sources"][1]["error"] == "source returned invalid collection result after 1 attempts"


def test_orchestrator_rejects_a_result_with_unregistered_audit_identity():
    good = StubAdapter("good", [source_result("good")])
    invalid = source_result("untrusted")
    invalid["source_url"] = "not-a-url"
    invalid["checked_at"] = "today"
    untrusted = StubAdapter("untrusted", [invalid])
    orchestrator = CollectionOrchestrator(
        SourceRegistry((registration(good), registration(untrusted))),
        retries=0,
        now=lambda: "2026-08-22T06:00:00+00:00",
    )

    result = asyncio.run(orchestrator.collect())

    assert result["counts"] == {"total": 2, "succeeded": 1, "failed": 1}
    assert result["sources"][0]["success"] is True
    assert result["sources"][1]["error"] == "source returned invalid collection result after 1 attempts"


def test_orchestrator_cancels_a_timed_out_adapter_before_retrying():
    class CancellableAdapter:
        source_id = "cancellable"
        source_name = "cancellable source"
        source_url = "https://cancellable.example.test"

        def __init__(self) -> None:
            self.calls = 0
            self.cancellations = 0

        async def collect(self) -> dict:
            self.calls += 1
            try:
                await asyncio.sleep(60)
            finally:
                self.cancellations += 1

    adapter = CancellableAdapter()
    orchestrator = CollectionOrchestrator(
        SourceRegistry((SourceRegistration(adapter, "collect_cancellable"),)),
        timeout_seconds=0.01,
        retries=1,
        now=lambda: "2026-08-22T06:00:00+00:00",
    )

    result = asyncio.run(orchestrator.collect())

    assert result["sources"][0]["error"] == "collection timed out after 2 attempts"
    assert adapter.calls == 2
    assert adapter.cancellations == 2


def test_mcp_orchestrator_tool_exposes_a_compact_summary_and_ephemeral_document(monkeypatch):
    from aichallenge_mcp import server

    class StubOrchestrator:
        async def collect(self) -> dict:
            return {
                "history_comparison": {
                    "available": False,
                    "reason": "No stored runs.",
                    "required_response_ko": "비교할 수 없습니다.",
                },
                "counts": {"total": 1, "succeeded": 1, "failed": 0},
                "sources": [],
            }

    monkeypatch.setattr(server, "orchestrator", StubOrchestrator())

    result = asyncio.run(server.collect_all_sources())

    assert result.structured_content == {
        "checked_at": None,
        "counts": {"total": 1, "succeeded": 1, "failed": 0},
        "item_count": 0,
        "sources": [],
        "document": {
            "file_name": "ai-contest-briefing-current.md",
            "mime_type": "text/markdown;charset=utf-8",
        },
    }
    assert "source 1/1 성공" in result.content[0].text
    assert "No stored runs." not in result.content[0].text
    assert result.meta is not None
    assert result.meta["briefing_document"]["content"].startswith("# AI 대회 브리핑")


def test_mcp_registers_each_registry_source_tool_and_the_orchestrator():
    from aichallenge_mcp import server

    tool_names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}

    assert "collect_all_sources" in tool_names
    assert {entry.public_tool_name for entry in server.source_registry.registrations} <= tool_names
