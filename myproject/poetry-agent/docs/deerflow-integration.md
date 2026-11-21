# DeerFlow Integration Contract

## Pinned runtime surface

The BFF uses the DeerFlow Gateway's documented run-admission interface:

```text
POST /api/runs/stream
```

The request declares `assistant_id=poetry-editor-lead`, a deterministic `thread_id=poetry-{task_id}`, metadata that correlates the local run/mandate, `on_disconnect=continue`, and a scoped idempotency key. It reads only the response `Content-Location` header to correlate the DeerFlow `thread_id` and `run_id`; it does not parse or trust model events as domain writes.

## Static agent package

The compose profile mounts:

```text
./deerflow-profile/agents → /runtime/agents:ro
```

The only static authoring agent is `poetry-editor-lead`. It sees the four local P0 skills and exactly one pinned MCP installation: `poetry-domain-mcp-v1`. It has no subagent allowlist in P0.

## Authentication

The BFF forwards `DEERFLOW_GATEWAY_TOKEN` only as `Authorization: Bearer …` to DeerFlow Gateway. This token is injected by the deployment platform, never stored in task records or source control. Local auth-disabled DeerFlow may omit it.

## Fail-closed behaviour

If the Gateway is disabled, unavailable, rejects the request, or fails to return the canonical run location, BFF changes the local run to `WAITING_FOR_RUNTIME`. It does not fabricate a proposal, retry through another framework, or bypass DeerFlow by calling a model directly.


## Runtime verification admission rule

The deployed `poetry-editor-lead` profile may read snapshots, request gap reports, and record a DRAFT proposal. It **cannot** call `apply_approved_draft`: the explicit user action in Poetry Studio is executed by BFF through the separate control bridge only after a persisted human review. This keeps review and application outside the DeerFlow credential boundary even if a model is prompted with a review identifier.

Before setting `DEERFLOW_ENABLED=true`, provision the official DeerFlow v2.2.0 source checkout (or an internally built image pinned to that checkout commit), Gateway credentials, `POETRY_DOMAIN_MCP_TOKEN`, and a distinct `POETRY_DOMAIN_CONTROL_TOKEN`; verify the latter is absent from the DeerFlow container environment.

## DeerFlow version pin

As verified from the official GitHub release feed on **November 6, 2026**, the selected runtime is
**DeerFlow v2.2.0** (released November 4, 2026). DeerFlow's official deployment builds its Gateway
from the release checkout rather than documenting a supported one-container `ghcr.io` runtime tag.
Run `make deerflow-bootstrap` to clone the exact `v2.2.0` tag into `content-agent/deploy/upstream/deer-flow-v2.2.0`; the
script records the resolved commit. The platform Compose file then builds the official
`backend/Dockerfile` from that pinned source. Do not substitute a floating `latest` image.
