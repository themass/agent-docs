#!/usr/bin/env bash
# Local checks before a commit: byte-compile, backend tests, frontend build.
# Does not seed, migrate or call live services.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "$ROOT/scripts/lib/project_paths.sh"
SERVER_ROOT="$(jc_server_root "$ROOT")"
WEB_ROOT="$(jc_web_root "$ROOT")"
cd "$SERVER_ROOT"
PYTHON="${JC_VERIFY_PYTHON:-$(jc_python "$ROOT")}"
if [[ ! -x "$PYTHON" ]]; then
  echo "FAIL: Python missing: $PYTHON" >&2
  exit 1
fi
"$PYTHON" -m compileall -q src tests "$ROOT/scripts"
"$PYTHON" -m pytest -q --tb=short
for script in "$ROOT"/scripts/*.sh "$ROOT"/scripts/lib/*.sh "$ROOT"/scripts/nginx/*.sh; do
  bash -n "$script"
done
(cd "$WEB_ROOT" && npm run build)

echo "PASS: local checks"
