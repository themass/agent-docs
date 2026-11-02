#!/usr/bin/env bash
# Copy the committed code of this clone into the deploy directory. Run as the web user, from
# the clone (wherever it is checked out); never as root.
#
#   ./scripts/publish.sh                    # copy
#   ./scripts/publish.sh --dry-run          # show what would be added, changed and removed
#   ./scripts/publish.sh --deploy           # copy, then run the deploy directory's deploy.sh
#   ./scripts/publish.sh --deploy --restart # ...and restart backend and frontend there
#   ./scripts/publish.sh --deploy -- --skip-frontend   # arguments after -- go to deploy.sh
#
# Target: /home/web/webroot/job-come (override with JC_DEPLOY_DIR).
#
# What gets copied is exactly the files git tracks at the current commit - so no .git, no
# node_modules, no half-edited or untracked files, and the same result on every run. The
# working tree must be clean for that to be true; --allow-dirty copies the files as they are
# on disk instead and says so in .deploy-version.
#
# Files are removed from the target only if an earlier publish put them there (.deploy-manifest
# lists them) and the commit no longer has them. Everything the target generates itself is
# never in that list and so is never touched: backend/server/.env, backend/server/.venv,
# frontend/web/node_modules, frontend/web/.next, .data.
#
# Running services keep working until they are restarted; a published change is live only
# after deploy.sh (dependencies, database migration, build) and the restart scripts.
set -euo pipefail

log() { printf '[publish] %s\n' "$*"; }
die() { printf '[publish] ERROR: %s\n' "$*" >&2; exit 1; }

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TARGET="${JC_DEPLOY_DIR:-/home/web/webroot/job-come}"

DRY_RUN=false
ALLOW_DIRTY=false
DO_DEPLOY=false
DO_RESTART=false
DEPLOY_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --allow-dirty) ALLOW_DIRTY=true ;;
    --deploy) DO_DEPLOY=true ;;
    --restart) DO_RESTART=true ;;
    -h | --help)
      sed -n '2,24p' "$0"
      exit 0
      ;;
    --)
      shift
      DEPLOY_ARGS=("$@")
      break
      ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

[[ "$(id -u)" -ne 0 ]] || die "run as the web user, not root: files copied as root cannot be updated by the user that runs the services"
command -v git >/dev/null 2>&1 || die "git is required"
command -v tar >/dev/null 2>&1 || die "tar is required"
git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1 || die "${SRC} is not inside a git checkout; publish from the clone"

mkdir -p "$TARGET" 2>/dev/null || die "cannot create ${TARGET} (does the web user own /home/web/webroot?)"
[[ -w "$TARGET" ]] || die "${TARGET} is not writable by $(id -un)"
TARGET="$(cd "$TARGET" && pwd -P)"
case "$TARGET/" in
  "$SRC/"* | "$SRC"/) die "the target (${TARGET}) is the source checkout or inside it" ;;
esac
case "$SRC/" in
  "$TARGET/"*) die "the source checkout (${SRC}) is inside the target (${TARGET})" ;;
esac

if [[ "$ALLOW_DIRTY" != true ]]; then
  dirty="$(git -C "$SRC" status --porcelain --untracked-files=no -- . | head -5)"
  if [[ -n "$dirty" ]]; then
    printf '%s\n' "$dirty" >&2
    die "uncommitted changes to tracked files (first lines above). Commit or stash them, or pass --allow-dirty"
  fi
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/publish.XXXXXX")"
trap '[[ -n "${WORK:-}" && -d "$WORK" ]] && rm -rf "$WORK"' EXIT

# Tracked files below this directory. Mode 160000 is a gitlink (a nested checkout such as a
# worktree pointer): tar would take it as a directory and copy whatever happens to be inside.
git -C "$SRC" ls-files -s -z -- . | while IFS= read -r -d '' record; do
  mode="${record%% *}"
  path="${record#*$'\t'}"
  [[ "$mode" == 160000 ]] && continue
  [[ "$path" == *$'\n'* ]] && die "a tracked path contains a newline: refusing"
  printf '%s\0' "$path"
done >"${WORK}/list.nul"
tr '\0' '\n' <"${WORK}/list.nul" | LC_ALL=C sort >"${WORK}/manifest.new"
[[ -s "${WORK}/manifest.new" ]] || die "git lists no tracked files under ${SRC}"

OLD_MANIFEST="${TARGET}/.deploy-manifest"
if [[ -f "$OLD_MANIFEST" ]]; then
  LC_ALL=C sort "$OLD_MANIFEST" >"${WORK}/manifest.old"
else
  : >"${WORK}/manifest.old"
fi
LC_ALL=C comm -13 "${WORK}/manifest.new" "${WORK}/manifest.old" >"${WORK}/removed"

added=0
changed=0
while IFS= read -r path; do
  if [[ ! -e "${TARGET}/${path}" && ! -L "${TARGET}/${path}" ]]; then
    added=$((added + 1))
  elif [[ -L "${SRC}/${path}" || -L "${TARGET}/${path}" ]]; then
    [[ "$(readlink "${SRC}/${path}" 2>/dev/null)" == "$(readlink "${TARGET}/${path}" 2>/dev/null)" ]] || changed=$((changed + 1))
  elif ! cmp -s "${SRC}/${path}" "${TARGET}/${path}"; then
    changed=$((changed + 1))
  fi
done <"${WORK}/manifest.new"
removed=$(wc -l <"${WORK}/removed" | tr -d ' ')

log "source:  ${SRC}"
log "target:  ${TARGET}"
log "commit:  $(git -C "$SRC" rev-parse --short HEAD) ($(git -C "$SRC" rev-parse --abbrev-ref HEAD))"
log "files:   $(wc -l <"${WORK}/manifest.new" | tr -d ' ') tracked, ${added} new, ${changed} changed, ${removed} to remove"
if [[ "$removed" -gt 0 ]]; then
  sed 's/^/           remove: /' "${WORK}/removed" | head -20
  [[ "$removed" -gt 20 ]] && log "           ... and $((removed - 20)) more"
fi

if [[ "$DRY_RUN" == true ]]; then
  log "dry run - nothing was written"
  exit 0
fi

# Copy through tar: it keeps the executable bit, needs no rsync on the server, and takes the
# names from a list so nothing outside the list can come along.
tar -C "$SRC" --null --no-recursion -cf - -T "${WORK}/list.nul" | tar -C "$TARGET" -xpf -

# Remove what the commit dropped. Only paths an earlier publish wrote, only files and
# symlinks, and never anything that points outside the target.
while IFS= read -r path; do
  case "$path" in "" | /* | ../* | */../* | */.. | ..) continue ;; esac
  if [[ -f "${TARGET}/${path}" || -L "${TARGET}/${path}" ]]; then
    rm -f "${TARGET:?}/${path}"
    dir="$(dirname "$path")"
    while [[ "$dir" != "." && "$dir" != "/" ]]; do
      rmdir "${TARGET}/${dir}" 2>/dev/null || break
      dir="$(dirname "$dir")"
    done
  fi
done <"${WORK}/removed"

cp "${WORK}/manifest.new" "$OLD_MANIFEST"
{
  printf 'commit: %s\n' "$(git -C "$SRC" rev-parse HEAD)"
  printf 'branch: %s\n' "$(git -C "$SRC" rev-parse --abbrev-ref HEAD)"
  printf 'published: %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')"
  printf 'source: %s\n' "$SRC"
  [[ "$ALLOW_DIRTY" == true ]] && printf 'dirty: %s\n' "$(git -C "$SRC" status --porcelain --untracked-files=no -- . | wc -l | tr -d ' ') tracked files differ from the commit"
} >"${TARGET}/.deploy-version"
log "published to ${TARGET}"

[[ -f "${TARGET}/backend/server/.env" ]] || log "NOTE: ${TARGET}/backend/server/.env does not exist yet - copy it from the old deployment, or from .env.example"
[[ -d "${TARGET}/frontend/web/.next" ]] || log "NOTE: ${TARGET}/frontend/web/.next does not exist yet - extract the prebuilt tarball there, or deploy.sh will build it"

if [[ "$DO_DEPLOY" == true ]]; then
  log "running deploy.sh in ${TARGET}"
  (cd "$TARGET" && ./scripts/deploy.sh ${DEPLOY_ARGS[@]+"${DEPLOY_ARGS[@]}"})
fi
if [[ "$DO_RESTART" == true ]]; then
  log "restarting services in ${TARGET}"
  (cd "$TARGET" && ./scripts/backend.sh restart && ./scripts/frontend.sh restart)
fi

if [[ "$DO_DEPLOY" != true && "$DO_RESTART" != true ]]; then
  log "next, in ${TARGET}:  ./scripts/deploy.sh  &&  ./scripts/backend.sh restart  &&  ./scripts/frontend.sh restart"
fi
