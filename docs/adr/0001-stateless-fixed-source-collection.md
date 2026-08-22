# ADR-0001: Use stateless, fixed-source collection with one orchestrator

- **Status:** Accepted
- **Date:** 2026-08-22

## Context

The original server centered on one contest site and SQLite-backed historical comparison. The product direction is instead a ChatGPT plugin that quickly collects current information from a small set of operator-curated websites. Users invoke the plugin; they do not supply a URL or manage data history.

## Decision

The server will be redesigned around these rules:

1. Sources are fixed registrations maintained by operators. Every source has a dedicated adapter and public MCP tool.
2. The ChatGPT Skill invokes one orchestrator only. The orchestrator runs all registered sources concurrently, applies per-source timeout/retry rules, and returns every source section separately.
3. Direct source tools remain model-callable for follow-up questions and return their complete native data shape.
4. The orchestrator does not merge or deduplicate items across sources. It returns source identity, canonical URL, collection timestamp, result, and failure details.
5. Collection is stateless. SQLite snapshots, new/changed comparisons, stale fallback, and archive/report workflows are outside scope and will be removed.
6. A source returning no valid records or violating its declared contract is a failure, not a successful empty result.
7. Access behavior is source-specific but limited to public, operator-approved access. No runtime user URLs, authentication bypass, CAPTCHA bypass, or private-data collection is supported.

## Consequences

- Calls always reflect a fresh collection run and do not depend on a local database.
- Partial failure is visible to ChatGPT instead of being hidden behind stale data.
- Adding a source requires adapter, registry, fixture, tests, and an initial live validation.
- Existing database-oriented MCP tools (`search`, `fetch`, historical overview, and change briefing) must be retired or redefined as part of the migration.
- The `@AI 대회 브리핑` experience remains simple: the Skill calls the orchestrator, then ChatGPT presents the collected information.
