from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Awaitable
from typing import Any, Protocol


class SourceAdapter(Protocol):
    source_id: str
    source_name: str
    source_url: str

    def collect(self) -> Awaitable[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class SourceRegistration:
    """One operator-maintained source adapter and its public MCP tool name."""

    adapter: SourceAdapter
    public_tool_name: str


class SourceRegistry:
    """The bounded, operator-curated set of collection sources."""

    maximum_sources = 20

    def __init__(self, registrations: tuple[SourceRegistration, ...]) -> None:
        if len(registrations) > self.maximum_sources:
            raise ValueError(f"at most {self.maximum_sources} sources may be registered")

        source_ids = [registration.adapter.source_id for registration in registrations]
        duplicate_source_ids = self._duplicates(source_ids)
        if duplicate_source_ids:
            raise ValueError(f"duplicate source_id: {duplicate_source_ids[0]}")

        public_tool_names = [registration.public_tool_name for registration in registrations]
        duplicate_tool_names = self._duplicates(public_tool_names)
        if duplicate_tool_names:
            raise ValueError(f"duplicate public tool name: {duplicate_tool_names[0]}")

        self.registrations = registrations

    @staticmethod
    def _duplicates(values: list[str]) -> list[str]:
        seen: set[str] = set()
        return [value for value in values if value in seen or seen.add(value)]
