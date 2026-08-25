---
name: ai-contest-briefing
description: "Use the installed AI 대회 브리핑 app to collect current data from every operator-registered AI competition source and brief it in Korean. Invoke explicitly for a current briefing, not general web research."
---

# AI 대회 브리핑

The user invoked this skill to receive a current Korean briefing from the installed **AI 대회 브리핑** app. Do not substitute general web search or prior chat content.

## Required execution

1. Locate the connected **AI 대회 브리핑** app and call `collect_all_sources` immediately, with no arguments. This is mandatory even if the user did not provide a written request after invoking the skill.
2. Treat `structuredContent.collection` as the complete current normalized data and `structuredContent.summary` as its compact status. This is fresh data, not a stored index or a comparison with earlier runs.
3. Use ChatGPT's native file/document creation capability to write the full result as one Markdown document when that capability is available. The document must preserve source sections, original URLs, success/failure states, warnings, errors, and all normalized item fields. The MCP app itself never creates or downloads a document.
4. Return a compact Korean briefing with the collection time, `N/M` source success count, total item count, and only failed-source errors or warnings. Link or attach the ChatGPT-created document. Do not reproduce every item in the chat.

## Safety and failure behavior

- This workflow only reads the app's operator-registered public sources. Do not perform unrelated web searches or browse user-supplied URLs.
- If `collect_all_sources` reports warnings or failed sources, state that the affected source needs confirmation. Never infer that a competition has closed or disappeared from a collection failure.
- Do not invent document contents that were not returned in `structuredContent.collection`. For a source-specific follow-up that needs full native fields, call that source's `collect_<source_id>` tool.
- If the app is unavailable, disconnected, or its tool call fails, say so plainly and stop. Do not provide a fabricated or web-search substitute briefing.
