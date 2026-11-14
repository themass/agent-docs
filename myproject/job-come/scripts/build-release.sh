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

REPO_ROOT="$(jc_repo_root "$JC_ROOT")" || die \
  "no repository root above ${JC_ROOT}.
       Building needs agentkit's source; a deployment host does not — it installs the
       committed wheels."
AGENTKIT="${REPO_ROOT}/libs/agentkit"
DEERFLOW_DIR="$(jc_vendor_deerflow "$JC_ROOT")"
SOURCE_RECORD="$(jc_deerflow_source_record "$JC_ROOT")"

# DeerFlow source is a BUILD input, not a dependency of the checkout.
#
# The wheels in `backend/server/wheels/` are the dependency — resolved by `uv sync`,
# installed on the deploy host, no source involved. Upstream is not on PyPI, so
# rebuilding those wheels means compiling from source; but that is something only a
# release does, and requiring the tree to be present made every plain
# `git clone && uv sync` fail for people who will never rebuild anything.
#
# So it is fetched on demand into a gitignored directory, pinned to the revision
# recorded in `wheels/DEERFLOW_SOURCE.txt`. A checkout that never builds never pays
# for it, and what gets built is still exactly the committed revision.
ensure_deerflow_source() {
  local url sha current
  [[ -d "${DEERFLOW_DIR}/backend/packages/harness" ]] && return 0

  [[ -f "$SOURCE_RECORD" ]] || die "missing ${SOURCE_RECORD} (records which revision to build)"
  read -r url sha < <(grep -vE '^\s*(#|$)' "$SOURCE_RECORD" | tail -1)
  [[ -n "$url" && -n "$sha" ]] || die "malformed ${SOURCE_RECORD}"

  log "fetching DeerFlow ${sha:0:8} from ${url}"
  mkdir -p "$(dirname "$DEERFLOW_DIR")"
  if [[ ! -d "${DEERFLOW_DIR}/.git" ]]; then
    rm -rf "$DEERFLOW_DIR"
    git init -q "$DEERFLOW_DIR"
    git -C "$DEERFLOW_DIR" remote add origin "$url"
  fi
  # Fetch by SHA: the pinned commit is what we build, and it need not be the tip of
  # any branch (an upstream may rewrite or move on). Depth 1 keeps it ~30 MB
  # instead of the full 200 MB history.
  git -C "$DEERFLOW_DIR" fetch --depth 1 -q origin "$sha" \
    || die "cannot fetch ${sha} from ${url} (network or the commit no longer exists)"
  git -C "$DEERFLOW_DIR" checkout -q FETCH_HEAD
  current="$(git -C "$DEERFLOW_DIR" rev-parse HEAD)"
  [[ "$current" == "$sha" ]] || die "checked out ${current}, expected ${sha}"
  log "DeerFlow source ready at ${DEERFLOW_DIR}"
}

# The three path-built packages and the import name each one actually ships. Kept
# together so the version check and the pin rewrite cannot disagree about a name.
PACKAGES=(
  "${AGENTKIT}"
  "${DEERFLOW_DIR}/backend/packages/harness"
  "${DEERFLOW_DIR}/backend/packages/extension-api"
)

command -v uv >/dev/null 2>&1 || die "uv is required (https://docs.astral.sh/uv/)"

# --- --check: does the committed wheel match the source it claims to be built from? ---
# Compares the CONTENT of the wheel against the source tree, not the version string.
#
# Version-only comparison shipped a broken release: `agentkit/observability/` was added
# without a version bump, so `--check` reported "ok agentkit 0.1.0", the deploy host
# installed the old wheel, and uvicorn died on `ModuleNotFoundError` — leaving the
# backend stopped until the wheels were rebuilt by hand. Equal versions are not equal
# contents, and catching exactly that is why this script exists.
#
# The comparison digests every file the package would ship, path included, so a new
# module, a deleted module and an edited module all show up. `__pycache__`/`.pyc` are
# skipped: they are build output, not source.
if [[ "$MODE" == "--check" ]]; then
  # Comparing a wheel against source necessarily needs source. Fetching it here is
  # not a compromise: a checkout that never verifies never pays for it either.
  ensure_deerflow_source
  PYTHON_CHECK="$(command -v python3 || true)"
  [[ -n "$PYTHON_CHECK" ]] || die "python3 not found; it compares wheels against source"
  "$PYTHON_CHECK" - "$WHEELS" "${PACKAGES[@]}" <<'PY_CHECK_WHEELS'
import hashlib
import re
import sys
import zipfile
from pathlib import Path

wheels = Path(sys.argv[1])
packages = [Path(p) for p in sys.argv[2:]]


def digest(entries):
    """One hash over (relative path, content) pairs, order-independent."""
    h = hashlib.sha256()
    for path, data in sorted(entries):
        h.update(path.encode())
        h.update(b"\0")
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


drift = 0
for pkg in packages:
    toml = (pkg / "pyproject.toml").read_text(encoding="utf-8")
    name = re.search(r'^name\s*=\s*"([^"]+)"', toml, re.M).group(1)
    version = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M).group(1)
    roots = re.search(r'^packages\s*=\s*\[([^\]]*)\]', toml, re.M)
    if not roots:
        print(f"UNKNOWN  {name}: no `packages` entry in pyproject.toml")
        drift = 1
        continue
    src_dirs = [
        pkg / p.strip().strip('"').strip("'")
        for p in roots.group(1).split(",")
        if p.strip()
    ]
    src_roots = {d.name: d for d in src_dirs if d.is_dir()}

    found = sorted(wheels.glob(f"{name.replace('-', '_')}-*.whl"))
    if not found:
        print(f"MISSING  {name} (no wheel in {wheels})")
        drift = 1
        continue
    wheel = found[0]

    source_entries = []
    for base in src_roots.values():
        for f in base.rglob("*"):
            if not f.is_file() or "__pycache__" in f.parts or f.suffix == ".pyc":
                continue
            source_entries.append((f.relative_to(base).as_posix(), f.read_bytes()))

    wheel_entries = []
    with zipfile.ZipFile(wheel) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            top, _, rest = info.filename.partition("/")
            if top not in src_roots or not rest:
                continue
            if rest.endswith(".pyc") or "__pycache__" in rest:
                continue
            wheel_entries.append((rest, z.read(info)))

    if digest(source_entries) == digest(wheel_entries):
        print(f"ok       {name} {version} ({len(source_entries)} files)")
        continue

    s_paths = {p for p, _ in source_entries}
    w_paths = {p for p, _ in wheel_entries}
    detail = []
    absent = sorted(s_paths - w_paths)
    if absent:
        detail.append("missing from wheel: " + ", ".join(absent[:5]))
    stale = sorted(w_paths - s_paths)
    if stale:
        detail.append("stale in wheel: " + ", ".join(stale[:5]))
    if not detail:
        detail.append("same file list, different contents")
    print(f"STALE    {name}: {version} content differs — {'; '.join(detail)}")
    drift = 1

sys.exit(1 if drift else 0)
PY_CHECK_WHEELS
  [[ $? == 0 ]] || die "wheels do not match the source — run $0 --update and commit them"
  exit 0
fi

# --- --update ---
ensure_deerflow_source
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
