---
name: ai-contest-briefing
description: "Use the installed AI 대회 브리핑 app to fetch a fresh aichallenge4all.or.kr competition briefing in Korean. Invoke explicitly for a current competition briefing, not general web research."
---

# AI 대회 브리핑

The user invoked this skill to receive a current Korean briefing from the installed **AI 대회 브리핑** app. Do not substitute general web search or prior chat content.

## Required execution

1. Locate the connected **AI 대회 브리핑** app and call `refresh_and_brief` immediately, with no arguments. This is mandatory even if the user did not provide a written request after invoking the skill.
2. Treat the returned JSON as the sole source of competition facts. Do not call `get_active_overview`, `search`, or `fetch` unless the first result needs an item-level clarification.
3. Return a concise Korean briefing in this order: collection time/result, 신규, 변경, 접수중, 진행중, 마감 임박, and warnings. Omit empty sections except collection result and warnings.

## Safety and failure behavior

- This workflow only reads the public `aichallenge4all.or.kr` site through the app. Do not perform unrelated web searches or browse other sites.
- If `refresh_and_brief` reports warnings, failed sources, or a failed run, state that the affected source needs confirmation. Never infer that a competition has closed or disappeared from a collection failure.
- If the app is unavailable, disconnected, or its tool call fails, say so plainly and stop. Do not provide a fabricated or web-search substitute briefing.
