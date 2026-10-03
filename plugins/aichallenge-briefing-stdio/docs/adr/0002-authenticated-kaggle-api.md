# ADR-0002: Use the authenticated Kaggle API for the Kaggle source

- **Status:** Accepted
- **Date:** 2026-08-25

## Context

Kaggle's anonymous browser listing route depends on browser-session and XSRF state. It is not a stable collection interface and no longer meets the source's access policy.

## Decision

`kaggle_competitions` uses Kaggle's official Python API client through the `kagglesdk` dependency. The adapter accepts only runtime credentials supplied by one of these environment-variable configurations, in priority order:

1. `KAGGLE_API_TOKEN`
2. `KAGGLE_USERNAME` and `KAGGLE_KEY` together

The server does not read, create, or persist a credential file. It does not fetch browser-session cookies or XSRF tokens. Missing, invalid, or failed credentials are a visible source failure, never an empty or closed catalogue.

Kaggle's authenticated listing response contains account-personalized fields such as whether the current account entered a competition and the account's rank. The adapter allowlists only public competition fields and never returns those personalized fields or credentials in MCP output.

The existing `location: Online` contract remains a public-metadata policy: listings whose public title, description, organizer, or category explicitly indicates offline participation are excluded. The Kaggle list API does not provide a first-class participation-location field.

## Consequences

- Operators must configure a Kaggle API credential only in the process environment before starting the local server.
- A valid configured credential is required for a live Kaggle collection smoke test.
- The collection remains limited to public competition data, despite authenticated API access.
