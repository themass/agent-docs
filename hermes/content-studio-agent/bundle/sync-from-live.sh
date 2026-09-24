#!/usr/bin/env bash
# Refresh bundle/profile from live ~/.hermes and ops from hermes-dev/scripts
set -euo pipefail
BUNDLE_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$BUNDLE_ROOT/env.sh"

"$BUNDLE_ROOT/profile/sync-from-live.sh"

OPS_SRC="$HERMES_DEV/scripts"
OPS_DST="$BUNDLE_ROOT/ops/scripts"
for f in sync-content-studio-secrets.sh sync-notebook-llm-credentials.py sync-mpt-llm-config.py \
  audit-llm-config.sh ali-tts-proxy.py volcano-tts-proxy.py verify-ali-tts-proxy.sh \
  content_studio_podcast_bootstrap.py fix-notebook-podcast-zh.py fix-notebook-speaker-voices.py \
  notebook-queue-maintain.py github-reports-browse.sh github_trending_snapshot.py; do
  [ -f "$OPS_SRC/$f" ] && cp -a "$OPS_SRC/$f" "$OPS_DST/"
done
chmod +x "$OPS_DST/"*.sh "$OPS_DST/"*.py 2>/dev/null || true

# Re-apply bundle-specific patches to sync script (copy from hermes-dev overwrites)
echo "Note: if sync-content-studio-secrets.sh was overwritten, re-run bundle maintainer patch or keep bundle copy."
cp "$HERMES_DEV/ports.env" "$BUNDLE_ROOT/stack/ports.env"
cp "$HERMES_DEV/PORTS.md" "$BUNDLE_ROOT/stack/PORTS.md"
echo "Done. Review: git status $BUNDLE_ROOT"
