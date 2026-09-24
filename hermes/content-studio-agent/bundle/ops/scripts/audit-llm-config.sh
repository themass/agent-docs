#!/usr/bin/env bash
# List files that may contain LLM API keys / base URLs (paths only, no secret values).
set -euo pipefail

ROOT="${DEEPAGENTS_ROOT:-/Users/gqli/work/deepagents}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
MPT_DIR="${MONEYPRINTER_DIR:-$ROOT/MoneyPrinterTurbo}"

echo "=== Content Studio LLM config locations ==="
echo ""
echo "[single source of truth]"
echo "  $HERMES_HOME/secrets.env"
echo ""
echo "[synced by sync-content-studio-secrets.sh]"
for f in \
  "$HERMES_HOME/.env" \
  "$HERMES_HOME/config.yaml" \
  "$ROOT/open-notebook/.env" \
  "$ROOT/openinspector/.env" \
  "$MPT_DIR/config.toml"; do
  if [[ -f "$f" ]]; then echo "  $f"; else echo "  $f (missing)"; fi
done
echo "  Open Notebook SurrealDB credentials (via API --notebook)"
echo ""
echo "[NOT synced — manual / env at runtime]"
echo "  $HERMES_HOME/auth.json (OAuth / credential pool metadata)"
echo "  examples/deep_research/agent.py (hardcoded)"
echo "  docs/*.md (examples only)"
echo "  deepagents-code ~/.deepagents/settings if used separately"
echo ""
echo "=== grep hits (file:line, redacted) ==="
patterns='openai_api_key|openai_base_url|CUSTOM_API_KEY|OPENAI_COMPATIBLE|LLM_API_KEY|newapi\.yuaiweiwu|8080/v1'
grep -RInE "$patterns" \
  "$HERMES_HOME/.env" \
  "$HERMES_HOME/secrets.env" \
  "$HERMES_HOME/config.yaml" \
  "$ROOT/open-notebook/.env" \
  "$ROOT/openinspector/.env" \
  "$MPT_DIR/config.toml" \
  2>/dev/null | sed -E 's/(sk-[A-Za-z0-9]{8})[A-Za-z0-9]+/\1…/g' || true
