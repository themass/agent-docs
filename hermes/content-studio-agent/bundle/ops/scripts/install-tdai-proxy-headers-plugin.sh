#!/usr/bin/env bash
# Install Content Studio TencentDB Proxy header plugin into Hermes (user plugins dir).
set -euo pipefail

OPS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$OPS_SCRIPT_DIR/../.." && pwd)"
PLUGIN_SRC="$BUNDLE_ROOT/hermes-plugin/tdai-proxy-headers"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
HERMES_GATEWAY_HOME="${HERMES_GATEWAY_HOME:-$HOME/.hermes}"
GATEWAY_PLUGINS_DIR="${HERMES_GATEWAY_HOME}/plugins"
PROFILE_PLUGINS_DIR="${HERMES_HOME}/plugins"
CONFIG="${HERMES_HOME}/config.yaml"

log() { echo "[tdai-plugin] $*"; }
warn() { echo "[tdai-plugin] WARN: $*" >&2; }

[[ -d "$PLUGIN_SRC" ]] || { warn "missing $PLUGIN_SRC"; exit 1; }
install_one() {
  local dir="$1"
  local target="${dir}/tdai-proxy-headers"
  mkdir -p "$dir"
  if [[ -e "$target" ]]; then
    rm -rf "$target"
  fi
  cp -R "$PLUGIN_SRC" "$target"
  log "Installed plugin → $target"
}

install_one "$GATEWAY_PLUGINS_DIR"
if [[ "$PROFILE_PLUGINS_DIR" != "$GATEWAY_PLUGINS_DIR" ]]; then
  install_one "$PROFILE_PLUGINS_DIR"
fi

if [[ -f "$CONFIG" ]]; then
  py="${DEEPAGENTS_PYTHON:-python3}"
  if [[ -z "${DEEPAGENTS_PYTHON:-}" && -f "$BUNDLE_ROOT/../../../scripts/deepagents-python.env.sh" ]]; then
    # shellcheck source=/dev/null
    source "$BUNDLE_ROOT/../../../scripts/deepagents-python.env.sh" 2>/dev/null || true
    py="${DEEPAGENTS_PYTHON:-python3}"
  fi
  "$py" - <<'PY' "$CONFIG"
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    from ruamel.yaml import YAML
except ImportError:
    print("ruamel.yaml missing; add tdai-proxy-headers to plugins.enabled manually", file=sys.stderr)
    raise SystemExit(0)

yaml = YAML()
data = yaml.load(path.read_text(encoding="utf-8")) or {}
plugins = data.get("plugins")
if not isinstance(plugins, dict):
    plugins = {}
    data["plugins"] = plugins
enabled = plugins.get("enabled")
if not isinstance(enabled, list):
    enabled = []
    plugins["enabled"] = enabled
name = "tdai-proxy-headers"
if name not in enabled:
    enabled.append(name)
with path.open("w", encoding="utf-8") as fh:
    yaml.dump(data, fh)
print(f"enabled plugin {name} in {path}")
PY
else
  warn "No config at $CONFIG — enable plugins.enabled: [tdai-proxy-headers] manually"
fi

log "Done. Restart Hermes Gateway so the plugin loads (e.g. stop/start Content Studio stack, or: hermes -p default gateway run --replace)."
log "Then run: bundle/ops/scripts/verify-content-studio-connectivity.sh"
