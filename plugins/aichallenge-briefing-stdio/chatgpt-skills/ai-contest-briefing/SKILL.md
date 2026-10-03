---
name: ai-contest-briefing
description: "Use the installed AI 대회 브리핑 app to collect current data from every operator-registered AI competition source and brief it in Korean. Invoke explicitly for a current briefing, not general web research."
---

# AI 대회 브리핑

The user invoked this skill to receive a current Korean briefing from the installed **AI 대회 브리핑** app. Do not substitute general web search or prior chat content.

## Required execution

1. Locate the connected **AI 대회 브리핑** app and call `collect_all_sources` immediately, with no arguments. This is mandatory even if the user did not provide a written request after invoking the skill.
2. Treat `structuredContent.collection` as the complete fresh current data and `structuredContent.summary` as its compact status. `collection` uses the lossless `aichallenge-mcp.columnar.v1` format: every source has `item_columns`, and each `item_rows` value maps to those columns by index. This is fresh data, not a stored index or a comparison with earlier runs.
3. On this initial invocation, return a compact Korean briefing: collection time, `N/M` source success count, total item count, meaningful failures/warnings, and at most 10 factual opportunities with the strongest returned urgency signals. Do not enumerate all competitions in the chat body. Do not read unrelated skill documentation.
4. In the same initial response, create and attach a machine-readable UTF-8 JSON file named `ai-contest-data-YYYY-MM-DD.json`, using the collection date when available. Its complete contents must be exactly `structuredContent.collection`, including its `format`, source metadata, `item_columns`, and every `item_rows` entry. State that this is the complete normalized collection data in the MCP's canonical columnar format; do not add or remove records or fields. This file is required even when every source fails, so users can inspect the reported source errors and warnings.
5. The full source data remains available in the tool result for this conversation. Create a reader-friendly Korean Markdown **full report** only when the user explicitly asks for a complete/full report or every collected competition. For that follow-up, use the existing columnar collection without recollecting unless it is no longer available in the conversation.

## Follow-up conversation

After the initial collection response, treat every subsequent user message as a normal ChatGPT follow-up. **Always write a visible Korean answer**; never end the turn after planning, reading instructions, creating a task, or displaying only a work-duration indicator.

- Reuse the current conversation's collected data and attached JSON file for questions about the listed competitions. Do not repeat `collect_all_sources`, regenerate the initial file, or invoke the initial-execution sequence unless the user explicitly asks to refresh/recollect current data.
- For a question whose answer is absent from the data, state that limitation plainly and give the most useful next step. Do not silently stop and do not substitute unrelated web research.
- For participation-fit questions or a request to conduct an interview, do not call an MCP tool. Start a short, friendly Korean interview in the response itself with these three questions: (1) your goal or topic area, (2) your current technical skills and preferred role, and (3) available time, team preference, and online/offline constraints. Use the answers in later turns to recommend only from the already-collected items, with explicit evidence and caveats.

## Report format

When a user explicitly requests the full report, write it in Korean with this exact information hierarchy. Use only facts in `structuredContent.collection`; do not add opinions, eligibility assumptions, or invented deadlines.

1. **제목과 기준 시각** — `AI 대회·해커톤 최신 브리핑` and the collection timestamp.
2. **한눈에 보기** — source success count, total item count, and only meaningful collection warnings.
3. **우선 확인할 기회** — concise bullets for actionable items whose returned status, deadline, or remaining time supports priority. Explain the factual signal (for example, an imminent returned deadline); do not rank items when the data has no priority signal.
4. **현재 참여 가능한 대회** — source-separated sections. For each item, present a compact table or consistent bullet card with title, status, deadline/remaining time, prize, organizer, location, and original link when those fields exist. Use Korean labels and omit unavailable fields instead of printing `null`, `-`, internal IDs, or raw objects.
5. **참고·준비중·연습 항목** — place non-actionable or practice/preparation entries in a shorter separate section so they do not obscure open opportunities.
6. **수집 상태와 주의사항** — source URL, success/failure, warnings, and errors. A failed source must be described as a collection issue, never as proof that a contest closed or disappeared.

Decode each `item_rows` entry against that source's `item_columns` before using its fields. Keep all useful normalized facts, but transform them into readable prose and tables. Do not dump every field verbatim, include transport/internal fields, or duplicate the same item in multiple sections. Name the file `ai-contest-briefing-report-YYYY-MM-DD.md` using the collection date when available.

## Safety and failure behavior

- This workflow only reads the app's operator-registered public sources. Do not perform unrelated web searches or browse user-supplied URLs.
- If `collect_all_sources` reports warnings or failed sources, state that the affected source needs confirmation. Never infer that a competition has closed or disappeared from a collection failure.
- Do not invent document contents that were not returned in `structuredContent.collection`. For a source-specific follow-up that needs full native fields, call that source's `collect_<source_id>` tool.
- If the app is unavailable, disconnected, or its tool call fails, say so plainly and stop. Do not provide a fabricated or web-search substitute briefing.
