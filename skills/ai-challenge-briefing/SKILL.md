---
name: ai-challenge-briefing
description: Collect a fresh Korean briefing of current AI competitions and hackathons from the local AI Challenge Briefing MCP.
---

# AI Challenge Briefing (Local)

Use the local `ai_challenge_briefing` MCP server whenever the user asks for a
current AI competition or hackathon briefing. This server is read-only and
collects only its operator-registered public sources.

## Workflow

1. Call `collect_all_sources` with no arguments for a new overall briefing.
2. Summarize the returned current data concisely in Korean: collection time,
   succeeded source count, item count, and meaningful source warnings.
3. List at most 10 concrete opportunities unless the user explicitly asks for
   all results or a source-specific detail.
4. For a later source-specific request, call only that source's
   `collect_<source_id>` tool.

## Boundaries

- Do not substitute web search, prior conversation data, or an assumed schedule
  for a collection request.
- This MCP is stateless. Never claim which competitions are new, changed,
  unchanged, removed, or closed compared with an earlier collection.
- A failed source is a collection failure, not proof that its competitions have
  closed or disappeared.
- The tools are read-only. Do not suggest that this plugin creates calendar
  events, stores results, or sends notifications.
