#!/usr/bin/env bash
# Rebuild the three prebuilt wheels that `backend/server/pyproject.toml` sources from
# `backend/server/wheels/`, update the version pins to match, and re-lock.
#
# Run this on a machine with the monorepo checkout — it needs the agentkit source and
# the vendored DeerFlow tree to build from. Everything it produces is committed, which
# is what lets a deployment host install with a plain `uv sync` and no source tree.
#
# Run it after ANY change to the vendored DeerFlow source or to libs/agentkit. A stale
# wheel is silently the old code, which is worse than a failed install: the app boots,
# imports succeed, and the fix is simply not there.
#
# Usage:
#   ./scripts/build-release.sh --update    # rebuild wheels, bump pins, re-lock
#   ./scripts/build-release.sh --check     # verify the committed wheels match the source
#
# `--check` is the one that belongs in CI: it fails if the source moved and nobody
# rebuilt, so the drift cannot reach a release.
set -euo pipefail

JC_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_ROOT="${JC_ROOT}/backend/server"
WHEELS="${SERVER_ROOT}/wheels"

# shellcheck source=lib/project_paths.sh
source "${JC_ROOT}/scripts/lib/project_paths.sh"

log() { printf '[wheels] %s\n' "$*"; }
die() { printf '[wheels] ERROR: %s\n' "$*" >&2; exit 1; }

MODE="${1:---update}"
case "$MODE" in
  --update|--check) ;;
  *) die "usage: $0 [--update|--check]" ;;
esac

MONOREPO_ROOT="$(jc_monorepo_root "$JC_ROOT")" || die \
  "no monorepo root above ${JC_ROOT}.
       Building needs libs/agentkit and the vendored DeerFlow tree; a deployment host
       does not have them and does not need them — it installs the committed wheels."
VENDOR="${MONOREPO_ROOT}/libs/agentkit"

# The three path-built packages and the import name each one actually ships. Kept
# together so the version check and the pin rewrite cannot disagree about a name.
PACKAGES=(
  "${VENDOR}"
  "${VENDOR}/vendor/deer-flow/backend/packages/harness"
  "${VENDOR}/vendor/deer-flow/backend/packages/extension-api"
)

command -v uv >/dev/null 2>&1 || die "uv is required (https://docs.astral.sh/uv/)"

# --- --check: does the committed wheel match the source it claims to be built from? ---
# Compares the wheel's own metadata against the pyproject that produced it. A version
# bump is the cheap signal; it will not catch an unversioned source edit, which is why
# --update is still the rule after touching vendor code, but it does catch the common
# case of "upstream synced, nobody rebuilt".
if [[ "$MODE" == "--check" ]]; then
  drift=0
  for pkg in "${PACKAGES[@]}"; do
    declared="$(grep -m1 '^version' "${pkg}/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')"
    name="$(grep -m1 '^name' "${pkg}/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')"
    wheelspec="$(ls "${WHEELS}/${name//-/_}-"*.whl 2>/dev/null | head -1 || true)"
    if [[ -z "$wheelspec" ]]; then
      log "MISSING  ${name} (no wheel in ${WHEELS})"; drift=1; continue
    fi
    built="$(basename "$wheelspec" | sed -E "s/^${name//-/_}-(.*)-py3-none-any\.whl$/\1/")"
    # Compare normalised, not raw: PEP 440 rewrites `2.3.0-dev` to `2.3.0.dev0` in the
    # filename, and a literal string compare reports that as staleness forever.
    norm() { printf '%s' "$1" | sed -E 's/-dev$/.dev0/; s/-([a-z]+)$/.\1/'; }
    if [[ "$(norm "$built")" != "$(norm "$declared")" ]]; then
      log "STALE    ${name}: source=${declared} wheel=${built}"; drift=1
    else
      log "ok       ${name} ${built}"
    fi
  done
  [[ "$drift" == 0 ]] || die "wheels are out of date — run $0 --update and commit them"
  exit 0
fi

# --- --update ---
mkdir -p "$WHEELS"
rm -f "${WHEELS}"/*.whl

for pkg in "${PACKAGES[@]}"; do
  name="$(grep -m1 '^name' "${pkg}/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')"
  log "building ${name}"
  ( cd "$pkg" && uv build --wheel --out-dir "$WHEELS" ) >/dev/null
done

ls -1 "$WHEELS"/*.whl | while read -r w; do log "  $(basename "$w")  $(du -h "$w" | cut -f1)"; done

# Point pyproject.toml at the exact filenames just produced. Derived from the files
# rather than reconstructed from a version string: egg-normalisation and local version
# segments make hand-written names drift, and a wrong filename here fails the lock
# rather than the build, which is a much later and more confusing place to learn it.
log "updating [tool.uv.sources]"
PYTHON="$(command -v python3 || true)"
[[ -n "$PYTHON" ]] || die "python3 not found; it writes the pyproject.toml pins"
"$PYTHON" - "$SERVER_ROOT" "$WHEELS" <<'PY'
import re, sys
from pathlib import Path

server, wheels = Path(sys.argv[1]), Path(sys.argv[2])
toml = server / "pyproject.toml"
found = {}
for w in sorted(wheels.glob("*.whl")):
    dist = w.name.split("-")[0].replace("_", "-").lower()
    found[dist] = w.name

expected = {"agentkit", "deerflow-harness", "deerflow-extension-api"}
missing = expected - set(found)
if missing:
    raise SystemExit(f"missing wheels for: {sorted(missing)}")

text = toml.read_text(encoding="utf-8")
for dist, filename in found.items():
    if dist not in expected:
        continue
    text = re.sub(
        rf'^{re.escape(dist)}\s*=\s*\{{\s*path\s*=\s*"[^"]*"\s*\}}$',
        f'{dist} = {{ path = "wheels/{filename}" }}',
        text,
        flags=re.M,
    )
toml.write_text(text, encoding="utf-8")
print("  pinned: " + ", ".join(f"{d}=wheels/{f}" for d, f in found.items() if d in expected))
PY

log "re-locking"
( cd "$SERVER_ROOT" && uv lock --refresh ) 2>&1 | tail -3

log "done — commit backend/server/wheels/ and backend/server/uv.lock"
