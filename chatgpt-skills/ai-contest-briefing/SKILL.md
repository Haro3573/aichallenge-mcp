---
name: ai-contest-briefing
description: "Use the installed AI 대회 브리핑 app to collect current data from every operator-registered AI competition source and brief it in Korean. Invoke explicitly for a current briefing, not general web research."
---

# AI 대회 브리핑

The user invoked this skill to receive a current Korean briefing from the installed **AI 대회 브리핑** app. Do not substitute general web search or prior chat content.

## Required execution

1. Locate the connected **AI 대회 브리핑** app and call `collect_all_sources` immediately, with no arguments. This is mandatory even if the user did not provide a written request after invoking the skill.
2. Treat the returned JSON as the sole source of competition facts. The result is a fresh collection run, not a stored index or a comparison with earlier runs.
3. Return a Korean briefing with the collection time and `N/M` source success count first. Then show every source in its own section, including its original URL and success/failure state. For successful sources, present all returned items without inventing or merging fields. For failed sources, state the error and warnings.

## Safety and failure behavior

- This workflow only reads the app's operator-registered public sources. Do not perform unrelated web searches or browse user-supplied URLs.
- If `collect_all_sources` reports warnings or failed sources, state that the affected source needs confirmation. Never infer that a competition has closed or disappeared from a collection failure.
- If the app is unavailable, disconnected, or its tool call fails, say so plainly and stop. Do not provide a fabricated or web-search substitute briefing.
