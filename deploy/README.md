# Public deployment runbook

This project is a **tool-only, stateless MCP server**. It can run behind any
managed container host or a self-managed container host, provided the final
endpoint is a stable public HTTPS URL such as `https://mcp.example.com/mcp`.

Secure MCP Tunnel remains appropriate for local development and staging. Do
not use a tunnel as the production endpoint submitted to the Plugins Directory.

## Required production configuration

Configure these values in the host's secret/config manager, never in Git:

| Setting | Purpose |
| --- | --- |
| `MCP_PRODUCTION=true` | Enables production readiness checks. |
| `MCP_ALLOWED_HOSTS=mcp.example.com` | Allows the exact public MCP host through SDK host validation. |
| `MCP_STATELESS_HTTP=true` | Allows requests to be served by any healthy replica. |
| `REQUIRE_KAGGLE_CREDENTIALS=true` | Fails readiness if the registered Kaggle source cannot authenticate. |
| `KAGGLE_API_TOKEN` | Operator-owned Kaggle service credential, supplied by the secret manager only. |

Managed hosts commonly set `PORT`; the server prefers it over `MCP_PORT`.

## Health checks

- `GET /healthz` confirms the process is live.
- `GET /readyz` confirms production-required host configuration and source
  credentials are present. It returns `503` with non-secret failure names when
  deployment configuration is incomplete.
- `POST /mcp` is the only MCP endpoint. Preserve streaming and do not buffer
  its Server-Sent Events at the load balancer or reverse proxy.

## Launch requirements

1. Build from the root with `docker build -t aichallenge-mcp .`.
2. Inject configuration and secrets through the hosting provider. The checked-in
   `.env.production.example` is documentation only.
3. Put TLS and a stable domain in front of the container. Allow the public
   domain in `MCP_ALLOWED_HOSTS`; do not expose a raw HTTP origin.
4. Configure edge rate limits and request-size limits before making the URL
   public. This server fetches a small fixed source list but does not persist
   results or implement user-level quotas.
5. Require `/readyz` to pass before traffic is sent to an instance. Keep at
   least one warm instance if cold-start latency is unacceptable.
6. Monitor HTTP status, MCP tool-call latency, source-specific failures, and
   container restarts. Do not enable raw HTTP body logging.

## Self-hosted reference

`docker-compose.production.yml` keeps the app on loopback. Pair it with a
TLS reverse proxy such as the Caddy example in this directory. On a managed
container host, use its native HTTPS ingress instead and do not run Caddy.

## Marketplace handoff

Before public submission, use the final production URL—not the local tunnel—to
scan tools in the Platform submission portal. The public listing also needs a
verified publisher identity, public website/support/privacy/terms URLs, domain
verification access, five positive tests, and three negative tests.
