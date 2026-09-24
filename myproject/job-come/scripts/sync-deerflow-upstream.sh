#!/usr/bin/env bash
# Sync AgentKit vendor deer-flow with bytedance/deer-flow upstream.
set -euo pipefail

JOB_COME_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DF="${JOB_COME_ROOT}/../libs/agentkit/vendor/deer-flow"

if [[ ! -d "${DF}/.git" ]]; then
  echo "Missing ${DF}"
  echo "Clone:"
  echo "  git clone --depth 1 https://github.com/bytedance/deer-flow.git ${DF}"
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
  echo "Then: ${JOB_COME_ROOT}/scripts/setup-venv.sh"
else
  echo "Already up to date with origin/main."
fi
