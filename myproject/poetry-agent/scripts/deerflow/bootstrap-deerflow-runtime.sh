#!/usr/bin/env bash
# Fetch the exact upstream DeerFlow release used by this platform. No floating branch and no latest tag.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${DEERFLOW_VERSION:-2.2.0}"
DEPLOY="$ROOT/content-agent/deploy"
DEST="${DEERFLOW_SOURCE_DIR:-$DEPLOY/upstream/deer-flow-v$VERSION}"
case "$DEST" in /*) ;; *) DEST="$DEPLOY/${DEST#./}" ;; esac
EXPECTED_TAG="v$VERSION"
if [[ -e "$DEST" ]]; then
  echo "Refusing to overwrite existing DeerFlow checkout: $DEST" >&2
  exit 2
fi
git clone --depth 1 --branch "$EXPECTED_TAG" https://github.com/bytedance/deer-flow.git "$DEST"
ACTUAL_TAG="$(git -C "$DEST" describe --tags --exact-match)"
[[ "$ACTUAL_TAG" == "$EXPECTED_TAG" ]] || { echo "Expected $EXPECTED_TAG, got $ACTUAL_TAG" >&2; exit 3; }
COMMIT="$(git -C "$DEST" rev-parse HEAD)"
printf 'repository=https://github.com/bytedance/deer-flow.git\nversion=%s\ntag=%s\ncommit=%s\n' "$VERSION" "$EXPECTED_TAG" "$COMMIT" > "$DEPLOY/upstream/deerflow.lock"
printf '%s\n' "$COMMIT" > "$DEST/.poetry-platform-source-commit"
printf 'DeerFlow %s prepared at %s\n' "$ACTUAL_TAG" "$DEST"
