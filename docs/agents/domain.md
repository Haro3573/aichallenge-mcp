# Domain docs

How engineering skills consume this repository's domain documentation.

## Before exploring

Read `CONTEXT.md` at the repository root when it exists, then read ADRs in `docs/adr/` relevant to the area being changed. If these files do not exist, proceed silently.

## Layout

This is a single-context repository.

```text
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

`/domain-modeling` creates `CONTEXT.md` and ADRs lazily when a term or decision needs to be recorded.

## Vocabulary and ADRs

Use vocabulary defined in `CONTEXT.md` consistently. If an intended change conflicts with an ADR, surface the conflict explicitly rather than silently overriding it.
