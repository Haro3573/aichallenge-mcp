---
name: ai-contest-briefing
description: "Use the installed AI 대회 브리핑 app to collect current data from every operator-registered AI competition source and brief it in Korean. Invoke explicitly for a current briefing, not general web research."
---

# AI 대회 브리핑

The user invoked this skill to receive a current Korean briefing from the installed **AI 대회 브리핑** app. Do not substitute general web search or prior chat content.

## Required execution

1. Locate the connected **AI 대회 브리핑** app and call `collect_all_sources` immediately, with no arguments. This is mandatory even if the user did not provide a written request after invoking the skill.
2. Treat `structuredContent.collection` as the complete current normalized data and `structuredContent.summary` as its compact status. This is fresh data, not a stored index or a comparison with earlier runs.
3. Use ChatGPT's native file/document creation capability to write one reader-friendly Korean Markdown **report** when that capability is available. This is an operator-facing briefing, never a raw JSON/data export. The MCP app itself never creates or downloads a document.
4. Return a compact Korean briefing with the collection time, `N/M` source success count, total item count, and only failed-source errors or warnings. Link or attach the ChatGPT-created document. Do not reproduce every item in the chat.

## Report format

Write the document in Korean with this exact information hierarchy. Use only facts in `structuredContent.collection`; do not add opinions, eligibility assumptions, or invented deadlines.

1. **제목과 기준 시각** — `AI 대회·해커톤 최신 브리핑` and the collection timestamp.
2. **한눈에 보기** — source success count, total item count, and only meaningful collection warnings.
3. **우선 확인할 기회** — concise bullets for actionable items whose returned status, deadline, or remaining time supports priority. Explain the factual signal (for example, an imminent returned deadline); do not rank items when the data has no priority signal.
4. **현재 참여 가능한 대회** — source-separated sections. For each item, present a compact table or consistent bullet card with title, status, deadline/remaining time, prize, organizer, location, and original link when those fields exist. Use Korean labels and omit unavailable fields instead of printing `null`, `-`, internal IDs, or raw objects.
5. **참고·준비중·연습 항목** — place non-actionable or practice/preparation entries in a shorter separate section so they do not obscure open opportunities.
6. **수집 상태와 주의사항** — source URL, success/failure, warnings, and errors. A failed source must be described as a collection issue, never as proof that a contest closed or disappeared.

Keep all useful normalized facts, but transform them into readable prose and tables. Do not dump every field verbatim, include transport/internal fields, or duplicate the same item in multiple sections. Name the file `ai-contest-briefing-report-YYYY-MM-DD.md` using the collection date when available.

## Safety and failure behavior

- This workflow only reads the app's operator-registered public sources. Do not perform unrelated web searches or browse user-supplied URLs.
- If `collect_all_sources` reports warnings or failed sources, state that the affected source needs confirmation. Never infer that a competition has closed or disappeared from a collection failure.
- Do not invent document contents that were not returned in `structuredContent.collection`. For a source-specific follow-up that needs full native fields, call that source's `collect_<source_id>` tool.
- If the app is unavailable, disconnected, or its tool call fails, say so plainly and stop. Do not provide a fabricated or web-search substitute briefing.
