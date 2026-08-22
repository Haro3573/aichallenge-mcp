# aichallenge-mcp context

## Purpose

`aichallenge-mcp` is a ChatGPT plugin for rapid collection of structured information from a small, operator-curated set of fixed web sources. Its initial domain is AI-related contests, hackathons, and challenges. It is not a general-purpose URL scraper and it does not accept URLs from end users at runtime.

## Ubiquitous language

| Term | Meaning |
| --- | --- |
| **source** | One operator-registered website or page family, identified by a stable `source_id`. |
| **source adapter** | Code that knows one source's access policy, extraction rules, required fields, and validation. |
| **source tool** | The public MCP tool exposing one source adapter's complete, source-specific result. It is model-callable for follow-up questions. |
| **orchestrator** | The single MCP tool invoked by the ChatGPT Skill. It runs every registered source adapter concurrently and returns all source sections, including failures. |
| **collection contract** | The source-specific definition of included records, required fields, access rules, and a valid result shape. |
| **collection run** | One fresh invocation of the orchestrator. Its output is current data only; it has no historical state. |
| **operator** | A maintainer who adds or changes registered sources in code and tests. This is not an end user. |

## Product boundaries

- Registered sources only; no arbitrary URL submission, crawling, login, CAPTCHA bypass, or private data access.
- Source scope begins with AI contests, hackathons, and challenges. Each adapter owns its inclusion and exclusion rules.
- The plugin is a quick lookup and collection tool. Interpretation, planning, reporting, and follow-up analysis belong to ChatGPT, not this MCP server.
- Source results are not deduplicated or merged by the server. The orchestrator preserves source sections so ChatGPT can compare them when useful.

## Runtime contract

- The Skill calls only the orchestrator.
- The orchestrator starts all registered sources in parallel. The operator keeps the set small (target maximum: 20 sources).
- Each source has a 20-second timeout and one retry. One failed source must not block successful source results.
- A source is successful only if it satisfies its collection contract. A zero-record result or required-field/shape failure is a collection failure, even when the HTTP request succeeded.
- The orchestrator reports each source's name, canonical URL, collection time, success/failure state, full result, and warning/error details.
- Direct source tools return their native, complete source-specific result without an imposed shared item schema.

## Historical state

The target architecture is stateless: no SQLite database, change tracking, stale fallback, stored snapshots, or previous-run comparison. Existing persistence-oriented code is legacy and must be removed or replaced during implementation.

## Source onboarding contract

Every new source ships as one change containing its adapter, public source tool, registry entry, fixture, and tests. The source must pass an initial live collection and validate its declared required fields before it is registered.
