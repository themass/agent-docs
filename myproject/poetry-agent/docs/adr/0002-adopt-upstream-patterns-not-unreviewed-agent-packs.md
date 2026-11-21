# ADR-0002: Adopt upstream patterns, not unreviewed agent packs

## Status
Accepted — 2026-11-06

## Context
Mature public repositories contain useful role definitions, skills, prompts and operational practices. Directly importing them would also import assumptions about tools, authority, publishing, data access and model behavior that conflict with the Poetry authoring boundary.

## Decision
Maintain a local upstream catalog and adoption-card review process. We may reference, template, adapt or integrate an upstream asset only according to its assigned lane. Local artifacts are versioned, immutable per Agent profile and subject to MCP/tool policy. No runtime download or whole-repository prompt import is allowed.

## Consequences
- We get leverage from external best practice without surrendering domain safety and provenance.
- Each adopted asset carries a small review cost.
- Upstream updates are consciously evaluated, never silently inherited.
