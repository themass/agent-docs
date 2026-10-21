# 2026-10-20 upload failure: ingestion reasoning policy

## Evidence

The supplied PDF is a three-page, text-native document. Local extraction produced text on all three pages (940, 799, and 179 characters); page inspection found no image-only page, so the pipeline correctly selected the native-text route and did not invoke OCR.

The failed run in `.data/logs/dev/api.log` showed the first `ingest_fast` attempt receiving 517 chunks with `content_chars=0` and `reasoning_chars=8978` before its 60-second stream budget expired. This is not a PDF extraction failure: the model was spending the complete structured-extraction attempt on hidden reasoning and never emitted JSON. The two fallback attempts then failed independently (timeout and upstream connection error).

## Change

`ingest_fast` now has an explicit, scenario-scoped generation policy in `backend/agent/llm/routing.yaml`:

- `reasoning_effort: none`
- `extra_body.thinking.type: disabled` for gateways that use the DeepSeek-compatible thinking switch
- Output ceiling now inherits `defaults.max_tokens: 100000` (see policy update below).

The router parses and propagates these fields into every resolved deployment, including manually consumed buffered streams. Writer/coach scenarios do not inherit this policy, so conversational agent thinking remains unchanged.

## Verification

- `tests/test_llm_router.py`, `tests/test_llm_transport.py`, and `tests/test_profile_structurer.py`: 18 passed.
- `git diff --check`: passed.
- The supplied PDF was inspected locally; no OCR was needed.

A live provider call was deliberately not issued automatically because it consumes paid gateway quota. The backend must be restarted once so the updated YAML is loaded; after restart, the first upload attempt should be checked for `reasoning_chars` staying near zero and `content_chars` becoming positive before the JSON validation phase.

## Token policy update (user request)

All business scenarios now inherit `defaults.max_tokens: 100000` in routing.yaml.
Removed the reviewer hardcoded 4096 and the harness hardcoded 8192/100000 to
avoid overriding the shared deployment policy. Endpoint-specific overrides remain
available for gateway-confirmed smaller limits. Context capacity (200000),
compaction trigger, and per-run usage budget (150000) are distinct controls and
were not mechanically replaced. The 100000 request is NOT proof that every gateway
alias accepts it; real gateway compatibility has not been verified. Increasing an
output ceiling does not fix the earlier reasoning-only timeout. Deadlines and
structured-response validation remain in place.
