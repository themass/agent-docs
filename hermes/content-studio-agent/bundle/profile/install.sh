#!/usr/bin/env bash
set -euo pipefail

# Install Content Studio Agent profile into ~/.hermes/profiles/content-studio
#
# Usage:
#   ./install.sh
#   ./install.sh /path/to/custom/profile

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HOME/.hermes/profiles/content-studio}"

echo "Installing Content Studio Agent profile to: $TARGET"
mkdir -p "$TARGET/reports" "$TARGET/logs/cron" "$TARGET/config" "$TARGET/docs"

rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$SCRIPT_DIR/skills/" "$TARGET/skills/"

rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$SCRIPT_DIR/scripts/" "$TARGET/scripts/"

chmod +x "$TARGET/scripts/"*.sh 2>/dev/null || true
find "$TARGET/skills/content-studio" -name '*.py' -exec chmod +x {} \; 2>/dev/null || true

if [ -f "$SCRIPT_DIR/SOUL.md" ]; then
  if [ ! -f "$TARGET/SOUL.md" ]; then
    cp "$SCRIPT_DIR/SOUL.md" "$TARGET/SOUL.md"
  else
    cp "$SCRIPT_DIR/SOUL.md" "$TARGET/SOUL.md.new"
    echo "Note: existing SOUL.md kept; new version saved as SOUL.md.new"
  fi
fi

if [ -f "$SCRIPT_DIR/profile.yaml" ]; then
  cp "$SCRIPT_DIR/profile.yaml" "$TARGET/profile.yaml"
fi

if [ ! -f "$TARGET/config/tts-providers.yaml" ] && [ -f "$SCRIPT_DIR/config/tts-providers.example.yaml" ]; then
  cp "$SCRIPT_DIR/config/tts-providers.example.yaml" "$TARGET/config/tts-providers.yaml"
  echo "Created $TARGET/config/tts-providers.yaml from example (edit before video/TTS)."
fi

if [ ! -f "$TARGET/config.yaml" ] && [ -f "$SCRIPT_DIR/config.yaml.example" ]; then
  cp "$SCRIPT_DIR/config.yaml.example" "$TARGET/config.yaml"
  echo "Created $TARGET/config.yaml from example — set model and api_key."
fi

if [ -f "$SCRIPT_DIR/docs/TTS_CONFIG.md" ]; then
  cp "$SCRIPT_DIR/docs/TTS_CONFIG.md" "$TARGET/docs/TTS_CONFIG.md"
fi

mkdir -p "$TARGET/scripts/dispatchers"
ln -sf "../../skills/content-studio/knowledge-library/assets/dispatcher_config.yaml" \
  "$TARGET/scripts/dispatchers/dispatcher_config.yaml"

echo ""
echo "Done. Next steps:"
echo "  1. cp hermes-dev/config/secrets.env.example $TARGET/secrets.env  # edit keys"
echo "  2. hermes-dev/scripts/sync-content-studio-secrets.sh"
echo "  3. export HERMES_HOME=$TARGET"
echo "  4. \"\$HERMES_HOME/scripts/content-studio.sh\" help"
echo ""
echo "Docs: docs/hermes/content-studio-agent/README.md"
