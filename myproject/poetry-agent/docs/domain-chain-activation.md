# Phase 2–3 activation sequence

This document is the deployment handoff for the real domain chain. It intentionally does not contain production credentials.

## Current database state

On **November 6, 2026**, the configured `vpn` schema on MySQL 5.6.40 received the V007 Agent domain schema: nine empty `poetry_agent_*` tables, V006/V007 version-ledger rows, and a C1–C9 audit with zero nonzero rows. Later on November 6, 2026, V008 added durable Poetry Studio task/run state and was applied successfully; it did not change poetry content. No poetry content was changed.

## Java host configuration

Inject these values into the host process environment/configuration; do not commit their values:

```text
poetry.enabled=true
poetry.agentInternalToken=<random deployment secret>
```

The internal token must equal `POETRY_AGENT_INTERNAL_TOKEN` injected into `poetry-domain-mcp`. It is not a browser value and must not be placed in Poetry Studio.

## Ordered live activation

1. Deploy the Java module containing the Agent controller and set the two properties above.
2. Start only `poetry-domain-mcp` and `agent-bff` with internal-only network access.
3. Confirm the Java snapshot and integrity-gap routes using the MCP service token.
4. Start DeerFlow only with the reviewed read/propose-only profile. `POETRY_DOMAIN_CONTROL_TOKEN` must be absent from this runtime.
5. In Poetry Studio, create one `GAP_ANALYSIS` for `work-chun-wang`; it must end at a reviewable DRAFT proposal.
6. Do not apply, publish, or compile content during the first runtime verification.

The user has requested that functional tests be collected for a later unified test pass; this plan therefore separates deployment admission from acceptance testing.

## V008 durable orchestration upgrade

V008 is the required follow-up to V007 before running Poetry Studio. It adds no poetry fact data
and no foreign keys. It persists BFF task metadata, run/mandate identifiers, DeerFlow runtime IDs,
run state, and append-only events. Apply it with:

```text
make migrate-agent-orchestration
```

The BFF remains stateless: it accesses these records only through the BFF → Poetry Domain MCP
control bridge → Java Agent Orchestration API path. It still never gets a database credential or the
Java internal-agent token.
