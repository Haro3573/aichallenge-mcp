from __future__ import annotations

import asyncio
import os


def test_keychain_token_is_loaded_only_when_missing(monkeypatch):
    from aichallenge_mcp import stdio

    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    monkeypatch.setenv("AICHALLENGE_MCP_KAGGLE_KEYCHAIN_SERVICE", "test-kaggle-service")
    observed: list[str | None] = []

    def fake_keychain_reader(service: str | None) -> str | None:
        observed.append(service)
        return "test-token"

    monkeypatch.setattr(stdio, "keychain_generic_password", fake_keychain_reader)

    stdio.load_kaggle_token_from_keychain()

    assert observed == ["test-kaggle-service"]
    assert os.environ["KAGGLE_API_TOKEN"] == "test-token"


def test_keychain_reader_is_not_called_when_token_is_already_available(monkeypatch):
    from aichallenge_mcp import stdio

    monkeypatch.setenv("KAGGLE_API_TOKEN", "already-in-environment")
    monkeypatch.setattr(
        stdio,
        "keychain_generic_password",
        lambda service: (_ for _ in ()).throw(AssertionError("must not read Keychain")),
    )

    stdio.load_kaggle_token_from_keychain()


def test_serve_uses_the_existing_mcp_registry(monkeypatch):
    from aichallenge_mcp import stdio

    observed: list[str] = []

    monkeypatch.setattr(stdio, "load_kaggle_token_from_keychain", lambda: observed.append("credentials"))

    async def fake_run_stdio() -> None:
        observed.append("stdio")

    monkeypatch.setattr(stdio.mcp, "run_stdio_async", fake_run_stdio)

    asyncio.run(stdio.serve())

    assert observed == ["credentials", "stdio"]
