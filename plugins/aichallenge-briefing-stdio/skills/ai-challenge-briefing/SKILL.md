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

## Optional Kaggle setup

If a Kaggle tool result says that `KAGGLE_API_TOKEN` (or legacy Kaggle
credentials) is not configured:

1. Explain that only the Kaggle source is unavailable; the other public
   sources can still be collected.
2. Ask whether the user wants to enable Kaggle on this Mac.
3. If they do, tell them to create a **Generic Password** in macOS Keychain
   Access with service name `aichallenge-mcp-kaggle`, any local account label,
   and their Kaggle API token as the password. Refer them to the repository
   README for the same steps.
4. Never ask the user to paste, reveal, display, write, or verify the token in
   chat, a command, a file, an environment variable, or an MCP call.

The configured Keychain service name is not secret. Its password is a secret:
the MCP reads it only into its child process memory at startup and must not
return it in a tool result.

## Boundaries

- Do not substitute web search, prior conversation data, or an assumed schedule
  for a collection request.
- This MCP is stateless. Never claim which competitions are new, changed,
  unchanged, removed, or closed compared with an earlier collection.
- A failed source is a collection failure, not proof that its competitions have
  closed or disappeared.
- The tools are read-only. Do not suggest that this plugin creates calendar
  events, stores results, or sends notifications.
