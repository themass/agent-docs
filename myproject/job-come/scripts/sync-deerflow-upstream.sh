#!/usr/bin/env bash
# Sync AgentKit vendor deer-flow with bytedance/deer-flow upstream.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
DF="$(jc_vendor_deerflow "$JC_ROOT")"
SOURCE_RECORD="$(jc_deerflow_source_record "$JC_ROOT")"

# The source tree only exists while a build needs it (see build-release.sh). If it is
# absent, there is nothing to compare against — say what the current pin is instead.
if [[ ! -d "${DF}/.git" ]]; then
  echo "No DeerFlow checkout at ${DF} (it is fetched on demand, not committed)."
  if [[ -f "$SOURCE_RECORD" ]]; then
    echo "Currently pinned:"
    grep -vE '^\s*(#|$)' "$SOURCE_RECORD" | tail -1
  fi
  echo "To compare with upstream, run a build first:"
  echo "  ./scripts/build-release.sh --check"
  exit 0
fi

cd "${DF}"
echo "==> remote"
git remote -v | head -2
echo "==> fetch origin"
git fetch origin main
echo "==> local $(git rev-parse --short HEAD)  upstream $(git rev-parse --short origin/main)"
BEHIND="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)"
if [[ "${BEHIND}" -gt 0 ]]; then
  git log --oneline HEAD..origin/main | head -15
  echo ""
  echo "Merge: cd ${DF} && git merge --ff-only origin/main"
  echo "Then rebuild and re-pin (this rewrites the local pin):"
  echo "  ${JC_ROOT}/scripts/build-release.sh --update --upstream \$(git -C ${DF} rev-parse HEAD)"
else
  echo "Already up to date with origin/main."
fi
