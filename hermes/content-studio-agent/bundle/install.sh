#!/usr/bin/env bash
set -euo pipefail
BUNDLE_ROOT="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$BUNDLE_ROOT/profile/install.sh" "$BUNDLE_ROOT/profile/sync-from-live.sh" 2>/dev/null || true
"$BUNDLE_ROOT/profile/install.sh" "$@"
echo ""
echo "Ops:  $BUNDLE_ROOT/ops/scripts/sync-content-studio-secrets.sh"
echo "Stack: $BUNDLE_ROOT/stack/start-content-studio-stack.sh"
