#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}}"
[ -d "$SRC/skills/content-studio" ] || { echo "missing $SRC/skills/content-studio" >&2; exit 1; }
echo "Sync: $SRC -> $SCRIPT_DIR"
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
  "$SRC/SOUL.md" "$SRC/profile.yaml" "$SCRIPT_DIR/"
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
  "$SRC/skills/content-studio/" "$SCRIPT_DIR/skills/content-studio/"
rsync -a --exclude '__pycache__' --exclude '*.pyc' \
  "$SRC/scripts/" "$SCRIPT_DIR/scripts/"
[ -f "$SRC/docs/TTS_CONFIG.md" ] && mkdir -p "$SCRIPT_DIR/docs" && cp "$SRC/docs/TTS_CONFIG.md" "$SCRIPT_DIR/docs/"
[ -f "$SRC/config/tts-providers.example.yaml" ] && cp "$SRC/config/tts-providers.example.yaml" "$SCRIPT_DIR/config/"
chmod +x "$SCRIPT_DIR/install.sh" "$SCRIPT_DIR/sync-from-live.sh" "$SCRIPT_DIR/scripts/"*.sh 2>/dev/null || true
echo "Done."
