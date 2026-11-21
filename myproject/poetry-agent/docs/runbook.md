# Operations Runbook

## A proposal is stuck in `WAITING_FOR_RUNTIME`

Expected when `DEERFLOW_ENABLED=false`. The bootstrap intentionally refuses to generate artificial model output. Configure a pinned DeerFlow runtime, its credentials, the profile mount, and an authenticated BFF-to-Gateway adapter before enabling it.

## Domain MCP returns `DOMAIN_API_UNAVAILABLE`

Check `POETRY_API_BASE_URL`, internal networking, Java API health and the platform-provided internal token. Do not retry by accessing MySQL directly.

## A reviewer approves a proposal

This creates an approval record and a `PENDING_DOMAIN_API` application state. It is not publish permission. Java API must later perform idempotent DRAFT application and produce audit receipt(s).

## Security response

If any environment exposes SQL, `publish`, `verify_source`, `set_verified`, or delete tools to a poetry authoring role, disable that profile, rotate its service credentials, preserve run receipts, and investigate configuration drift.

## MySQL 5.6 V007 migration recovery (November 6, 2026)

The configured database is MySQL **5.6.40**, whose 767-byte index limit rejects a `utf8mb4` unique key built from `VARCHAR(48) + VARCHAR(200)`. V007 therefore constrains `poetry_agent_tool_receipt.idempotency_key` to **128** characters. If an old first attempt has committed only part of V007 DDL, use `scripts/db/migrate-agent-domain.sh`; it recognizes only the documented zero-, five-, or nine-table pre-ledger states, snapshots the Poetry schema, and uses the narrowly scoped recovery SQL. It refuses every other state.

The script’s C1–C9 check must use batch output (`-N -B`), not the human table format (`-t`); otherwise zero rows are incorrectly parsed as failures.

