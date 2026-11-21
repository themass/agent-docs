# Poetry Agent Extension

This package is intentionally a **governance extension**, not a second domain service. It must be installed into the selected DeerFlow runtime through its extension lifecycle once the pinned DeerFlow version and `deerflow-extension-api` compatibility are finalized.

It provides only orchestration tools:

- `issue_mandate`
- `delegate_poetry_task`
- `record_proposal`
- `request_human_review`
- `read_review_decision`
- `validate_proposal_schema`
- `redact_untrusted_material`
- `budget_guard`
- `compose_scene_compile_request`

It must never expose domain mutation, database, publishing, source-verification, or deletion tools. Domain writes remain MCP → Java Poetry API operations.
