# ADR-0001: DeerFlow executes agents; Java Poetry API owns domain authority

## Status
Accepted — 2026-11-06

## Context
The project requires long-running editorial agents while preserving traceable poetry facts, DRAFT-only authoring, no database foreign keys, manual source verification and a separate Scene Bundle publication gate.

## Decision
Use DeerFlow as the Agent runtime and integrate it through a restricted HTTP MCP service. All factual reads and any DRAFT applications pass through Java Poetry API. DeerFlow, BFF and MCP have no MySQL credentials. Publication and source verification tools do not exist in the Agent tool surface.

## Consequences
- DeerFlow upgrades remain separable from content-domain releases.
- Java API must expose idempotent, audited domain endpoints before production authoring is enabled.
- More cross-service calls are accepted in exchange for a clear authority boundary.
