#!/usr/bin/env bash
# Build a self-contained deployment artifact: wheels for the three in-repo packages
# plus a frozen requirements.txt for everything else.
#
# Run this ON A MACHINE THAT HAS THE MONOREPO CHECKOUT (the dev box), then copy
# `dist/` to the server. The server then needs no source tree at all — which is the
# point: `backend/server/pyproject.toml` declares `agentkit`, `deerflow-harness` and
# `deerflow-extension-api` as `{ path = ..., editable = true }`, so a plain
# `uv sync` on a deployment host can only work if it has the entire monorepo source
# including the vendored DeerFlow tree. That is a build-time concern, not a runtime one.
#
# Usage:
#   ./scripts/build-release.sh            # writes ./dist
#   ./scripts/build-release.sh --clean    # wipe dist first
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
DIST="${JC_RELEASE_OUT:-${JC_ROOT}/dist}"

# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"

# Located by walking up rather than by a fixed `../../../`, because the project is not
# always at the same depth: a git worktree nests it two levels deeper than the main
# checkout, and the hardcoded relative path silently resolves to the wrong place there.
# This is the same search the rest of the scripts use.
MONOREPO_ROOT="$(jc_monorepo_root "$JC_ROOT")" || {
  printf '[release] ERROR: no monorepo root above %s (needs libs/agentkit + venv)\n' \
    "$JC_ROOT" >&2
  printf '[release] This script must run inside the monorepo checkout, not on the server.\n' >&2
  exit 1
}

# The three path dependencies, relative to the monorepo root. Kept in one place so a
# fourth one added to pyproject.toml is a one-line change here rather than a silent
# "requirements installed but the app cannot import it" at runtime.
VENDOR="${MONOREPO_ROOT}/libs/agentkit"
PACKAGES=(
  "${VENDOR}"
  "${VENDOR}/vendor/deer-flow/backend/packages/harness"
  "${VENDOR}/vendor/deer-flow/backend/packages/extension-api"
)

log() { printf '[release] %s\n' "$*"; }
die() { printf '[release] ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$*" == *--clean* ]] && rm -rf "$DIST"

command -v uv >/dev/null 2>&1 || die "uv is required (https://docs.astral.sh/uv/)"
for pkg in "${PACKAGES[@]}"; do
  [[ -f "${pkg}/pyproject.toml" ]] \
    || die "missing in-repo package: ${pkg}
       This script must run inside the monorepo checkout, not on the server."
done

mkdir -p "$DIST"

# 1. Wheels for the in-repo packages.
#
# Built from source rather than taken from the existing venv on purpose: an editable
# install's metadata goes stale the moment the package's `version` changes, so
# `importlib.metadata.version()` in the dev venv can report 2.1.0 while the code
# actually being imported is 2.3.0-dev. A wheel built from the tree is the only thing
# guaranteed to match what the dev environment runs.
for pkg in "${PACKAGES[@]}"; do
  name="$(basename "$pkg")"
  log "building wheel: ${name}"
  ( cd "$pkg" && uv build --wheel --out-dir "$DIST" ) >/dev/null
done

# 2. Everything else, frozen and without the three local packages.
#
# `--no-emit-project` drops the `jc` project itself, but NOT its path dependencies:
# the export still carries them as `-e ../../../../../libs/agentkit` lines, which point
# at a monorepo that will not exist on the server. Verified the hard way — the first
# version of this script shipped exactly those lines and the server-side install died
# with `Distribution not found at: file:///.../libs/agentkit`.
#
# They are stripped here rather than depended on being absent, and the guard below
# checks the result instead of the command's intent. The wheels installed separately
# in step 3 are what satisfy them.
log "exporting frozen requirements"
( cd "$SERVER_ROOT" && uv export --frozen --no-dev --no-emit-project \
    --format requirements-txt -o "${DIST}/requirements.txt" ) >/dev/null

# Drop any line that resolves to a local path: `-e ../../..`, `pkg @ file:///...`,
# `--find-links ./...`. Registry pins are `name==version` and never match.
filtered="${DIST}/requirements.txt.filtered"
grep -vE '^[[:space:]]*-e[[:space:]]|@[[:space:]]*file:|file://|^[[:space:]]*--find-links' \
  "${DIST}/requirements.txt" > "$filtered"
mv "$filtered" "${DIST}/requirements.txt"

# Fail loudly rather than shipping an artifact that only installs on the build machine.
if grep -qE 'file://|^-[[:space:]]*-e|libs/agentkit' "${DIST}/requirements.txt"; then
  die "requirements.txt still references the monorepo source tree:
$(grep -nE 'file://|-e |libs/agentkit' "${DIST}/requirements.txt" | head -5)
       A server without the checkout could not install it."
fi

# 3. A manifest, so a deployed host can answer "which code is this?" without git.
{
  printf 'built_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'built_from=%s\n' "$JC_ROOT"
  printf 'git_commit=%s\n' "$(git -C "$JC_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf 'git_dirty=%s\n' "$(test -n "$(git -C "$JC_ROOT" status --porcelain 2>/dev/null)" && echo yes || echo no)"
} > "${DIST}/RELEASE"

log "artifact ready: ${DIST}"
ls -1 "$DIST"
