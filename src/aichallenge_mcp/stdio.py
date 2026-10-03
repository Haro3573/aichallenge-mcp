"""Codex-local stdio entry point for the AI Challenge Briefing MCP.

This mode deliberately has no HTTP listener, Secure MCP Tunnel client, or
LaunchAgent dependency. Codex starts the process and exchanges MCP JSON-RPC
messages through its standard input and output streams.
"""

from __future__ import annotations

import asyncio
import os

from .runtime import (
    KAGGLE_API_TOKEN_ENV,
    KAGGLE_KEYCHAIN_SERVICE_ENV,
    keychain_generic_password,
)
from .server import mcp


def load_kaggle_token_from_keychain() -> None:
    """Populate the child-process-only Kaggle token when a service is configured.

    The service name is configuration, not a credential. The password is never
    printed, persisted, or included in any MCP response.
    """
    if os.getenv(KAGGLE_API_TOKEN_ENV):
        return

    service = os.getenv(KAGGLE_KEYCHAIN_SERVICE_ENV)
    token = keychain_generic_password(service)
    if token:
        os.environ[KAGGLE_API_TOKEN_ENV] = token


async def serve() -> None:
    """Run the existing MCP tool registry over the local stdio transport."""
    load_kaggle_token_from_keychain()
    await mcp.run_stdio_async()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
