#!/usr/bin/env bash
# Sync AgentKit vendor deer-flow with bytedance/deer-flow upstream.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"
DF="$(jc_vendor_deerflow "$JC_ROOT")" || {
  echo "Cannot find the repository root (libs/agentkit) above ${JC_ROOT}" >&2
  exit 1
}

if [[ ! -d "${DF}/.git" ]]; then
  echo "Missing ${DF}"
  echo "It is a git submodule; initialise it:"
  echo "  git submodule update --init --recursive"
  exit 1
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
  echo "Then: ${JC_ROOT}/scripts/setup-venv.sh"
else
  echo "Already up to date with origin/main."
fi
