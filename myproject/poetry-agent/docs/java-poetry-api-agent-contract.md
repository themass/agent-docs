# Java Poetry API ↔ Poetry Domain MCP Contract v1

> **Status:** Java implementation started on **November 6, 2026**. Java Poetry API remains the content authority; DeerFlow/MCP/BFF never receive a database credential.

## Authentication and correlation

Every request from `poetry-domain-mcp` must include:

```text
X-Poetry-Agent-Internal-Token: deployment secret
X-Poetry-Agent-Role: CONTENT_EDITOR | HISTORICAL_REVIEWER  (audit context only)
X-Poetry-Agent-Run-Id: run_…
X-Poetry-Agent-Mandate-Id: mandate_…
Idempotency-Key: opaque stable request key
```

The deployment-bound internal token authenticates the caller. Role is retained for audit only; no role supplied by an LLM is an authorization decision.

## Endpoints

| Method | Path | Caller | Purpose | State effect |
|---|---|---|---|---|
| `GET` | `/api/poetry/v1/works/{workId}/snapshot` | MCP | Canonical editorial snapshot, including DRAFT | none |
| `GET` | `/api/poetry/v1/works/{workId}/integrity-gap-report` | MCP | Server-observed data and audit gaps | none |
| `POST` | `/api/poetry/v1/draft/proposals` | MCP | Store one structured DRAFT candidate | DRAFT candidate only |
| `POST` | `/api/poetry/v1/draft/proposals/{proposalId}/reviews` | BFF only | Persist human APPROVE/REJECT decision | Agent audit record |
| `POST` | `/api/poetry/v1/draft/proposals/{proposalId}/apply` | MCP after BFF review | Apply approved executable operations | DRAFT rows only |
| `POST` | `/api/poetry/v1/works/{workId}/compile-requests` | MCP | Record compiler-eligibility review request | request/review record only |

The review endpoint is intentionally absent from MCP tools: **a DeerFlow agent cannot approve its own work**.

## Executable proposal payload

A proposal always remains a human-readable candidate. In v1, only an optional `changes[].draft_payload` with `operation=CREATE_ANNOTATION` can be executed after a persisted human approval. It is independently revalidated by Java and calls the existing DRAFT authoring service. All other change types (`GAP_REPORT`, `BACKGROUND`, `CLAIM`, `SCRIPT`) remain editorial candidates and are recorded as retained, non-mutating changes.

This incremental policy avoids pretending that generic model prose is a safe content mutation language.

## Forbidden capabilities

The Agent-facing API exposes **none** of:

```text
publish
retract
verify_source
set_verified
delete_content
execute_sql
```

## Response envelope

```json
{
  "status": "OK | REJECTED | REVIEW_REQUIRED | CONFLICT",
  "data": {},
  "audit_refs": ["audit_…"],
  "next_action": "NONE | HUMAN_REVIEW | REPLAN"
}
```

`status=OK` on apply means only that the approved operations wrote **DRAFT** rows. It never proves a fact, source, script, Bundle, or work is published.

## Persistence and integrity

V007 adds `poetry_agent_*` records for mandates, proposals, reviews, idempotency receipts, events, profiles, and compiler eligibility. There are **zero foreign keys**. Service-side checks, unique keys, transactional state transitions and C9 audit queries provide the association checks. V008 extends the same no-foreign-key model with durable Studio task/run state and runtime correlation IDs.

## Durable orchestration API (V008, MCP control bridge only)

These endpoints are **not MCP tools** and are **not exposed to DeerFlow**. Poetry Studio reaches them
only through the separate BFF → Domain MCP control bridge, using a control credential distinct from
the DeerFlow MCP credential.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/poetry/v1/agent-orchestration/tasks` | Persist bounded Studio task metadata |
| `GET` | `/api/poetry/v1/agent-orchestration/tasks/{id}` | Recover a task after BFF restart |
| `POST` | `/api/poetry/v1/agent-orchestration/tasks/{id}/runs` | Create run, mandate, profile receipt and `RUN_CREATED` event atomically |
| `GET` | `/api/poetry/v1/agent-orchestration/runs/{id}` | Recover durable run state |
| `PUT` | `/api/poetry/v1/agent-orchestration/runs/{id}/admission` | Record DeerFlow runtime correlation or explicit unavailability |
| `PUT` | `/api/poetry/v1/agent-orchestration/runs/{id}/state` | Advance bounded workflow state |
| `POST/GET` | `/api/poetry/v1/agent-orchestration/runs/{id}/events` | Append / cursor-read immutable operational events |
| `GET` | `/api/poetry/v1/agent-orchestration/proposals/{id}` | Recover proposal and review/application state |

The orchestration service has no content mutation endpoint. Proposal persistence, review, and the
single allowed DRAFT application remain on the restricted V007 domain endpoints.
