# ADR 0003: Deliver full collection runs as ephemeral Markdown downloads

## Status

Accepted

## Context

The operator may register up to 20 fixed sources. Returning every normalized item in `collect_all_sources` makes the model-facing conversation payload grow with the source set and makes the ChatGPT transcript difficult to use reliably. The product is intentionally stateless, so storing exports or adding a document database would violate the lightweight architecture.

## Decision

`collect_all_sources` returns only a compact status summary to the model and conversation. The full normalized collection is rendered in-memory as Markdown and placed in that tool result's `_meta.briefing_document` payload. An MCP Apps resource associated with the tool receives this metadata and offers a user-initiated browser download.

The Markdown is not written to a server file, database, snapshot store, or archive. Raw adapter transport payloads are excluded from the document; normalized public fields, source audit details, warnings, and failures remain available.

## Consequences

- The ChatGPT conversation remains bounded as source count and item volume increase.
- Users can retain one complete document per invocation when they choose to download it.
- Clients that do not render MCP Apps receive only the compact summary; direct source tools remain available for targeted follow-up.
- Browser download requires a user click, which is more reliable and safer than attempting an automatic sandboxed download.
