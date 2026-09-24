#!/usr/bin/env bash
# Fail if runtime/hooks branch on persisted chat `kind` (UI uses TraceView.variant).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
hits="$(rg 'message\.kind|record\.kind' "$root/packages/runtime" "$root/apps/extension/src/chat" "$root/apps/extension/src/lib/agent-event-projection.ts" 2>/dev/null || true)"
if [ -n "$hits" ]; then
  echo "check-trace-kind: forbidden kind branches:" >&2
  echo "$hits" >&2
  exit 1
fi
echo "check-trace-kind ok"
