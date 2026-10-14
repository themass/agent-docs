# Content Studio bundle — path constants (source from any bundle script).
# Layout: docs/hermes/content-studio-agent/bundle/
if [[ -z "${CONTENT_STUDIO_BUNDLE_ROOT:-}" ]]; then
  CONTENT_STUDIO_BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
BUNDLE_ROOT="$CONTENT_STUDIO_BUNDLE_ROOT"
# docs/hermes/content-studio-agent/bundle -> monorepo root (deepagents)
REPO_ROOT="${REPO_ROOT:-$(cd "$BUNDLE_ROOT/../../../.." && pwd)}"
# Sibling checkout root (open-notebook / MoneyPrinterTurbo live next to deepagents).
WORK_ROOT="${WORK_ROOT:-$(cd "$REPO_ROOT/.." && pwd)}"
HERMES_DEV="${HERMES_DEV:-$REPO_ROOT/hermes-dev}"

# Prefer a checkout inside the monorepo; otherwise the sibling under WORK_ROOT.
_cs_pick_dir() {
  local inside="$1"
  local sibling="$2"
  if [[ -d "$inside" ]]; then
    printf '%s\n' "$inside"
  elif [[ -d "$sibling" ]]; then
    printf '%s\n' "$sibling"
  else
    printf '%s\n' "$inside"
  fi
}

OPEN_NOTEBOOK_DIR="${OPEN_NOTEBOOK_DIR:-$(_cs_pick_dir "$REPO_ROOT/open-notebook" "$WORK_ROOT/open-notebook")}"
MONEYPRINTER_DIR="${MONEYPRINTER_DIR:-$(_cs_pick_dir "$REPO_ROOT/MoneyPrinterTurbo" "$WORK_ROOT/MoneyPrinterTurbo")}"
OPENINSPECTOR_DIR="${OPENINSPECTOR_DIR:-$(_cs_pick_dir "$REPO_ROOT/openinspector" "$WORK_ROOT/openinspector")}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
HERMES_WEBUI_DIR="${HERMES_WEBUI_DIR:-$HERMES_DEV/hermes-webui}"
HERMES_STUDIO_DIR="${HERMES_STUDIO_DIR:-$HERMES_DEV/hermes-studio}"
