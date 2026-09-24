# Content Studio bundle — path constants (source from any bundle script).
# Layout: docs/hermes/content-studio-agent/bundle/
if [[ -z "${CONTENT_STUDIO_BUNDLE_ROOT:-}" ]]; then
  CONTENT_STUDIO_BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
BUNDLE_ROOT="$CONTENT_STUDIO_BUNDLE_ROOT"
# docs/hermes/content-studio-agent/bundle -> monorepo root (deepagents)
REPO_ROOT="${REPO_ROOT:-$(cd "$BUNDLE_ROOT/../../../.." && pwd)}"
HERMES_DEV="${HERMES_DEV:-$REPO_ROOT/hermes-dev}"
OPEN_NOTEBOOK_DIR="${OPEN_NOTEBOOK_DIR:-$REPO_ROOT/open-notebook}"
MONEYPRINTER_DIR="${MONEYPRINTER_DIR:-$REPO_ROOT/MoneyPrinterTurbo}"
OPENINSPECTOR_DIR="${OPENINSPECTOR_DIR:-$REPO_ROOT/openinspector}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
