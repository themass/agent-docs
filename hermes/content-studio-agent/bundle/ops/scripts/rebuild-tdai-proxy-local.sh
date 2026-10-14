#!/usr/bin/env bash
# Build Memory Proxy from local TencentDB-Agent-Memory source and restart tdai-proxy.
set -euo pipefail

TDAI_MEMORY_DIR="${TDAI_MEMORY_DIR:-/Users/gqli/work/TencentDB-Agent-Memory}"
DEPLOY="${TDAI_DEPLOY_DIR:-$TDAI_MEMORY_DIR/deploy/global-images}"
TAG="${TDAI_PROXY_LOCAL_TAG:-agentmemory/memory-proxy:local}"

[[ -f "$TDAI_MEMORY_DIR/MemoryProxy/Dockerfile" ]] || {
  echo "Missing MemoryProxy Dockerfile under $TDAI_MEMORY_DIR" >&2
  exit 1
}

echo "[rebuild-proxy] docker build -t $TAG ..."
docker build -t "$TAG" "$TDAI_MEMORY_DIR/MemoryProxy"

ENV_FILE="${ENV_FILE:-$DEPLOY/.env}"
if [[ -f "$ENV_FILE" ]]; then
  if grep -q '^PROXY_IMAGE=' "$ENV_FILE"; then
    sed -i '' "s|^PROXY_IMAGE=.*|PROXY_IMAGE=$TAG|" "$ENV_FILE"
  else
    echo "PROXY_IMAGE=$TAG" >>"$ENV_FILE"
  fi
  echo "[rebuild-proxy] PROXY_IMAGE=$TAG in $ENV_FILE"
fi

if [[ -x "$DEPLOY/start-proxy.sh" ]]; then
  (cd "$DEPLOY" && docker rm -f tdai-proxy 2>/dev/null || true; PROXY_FULL_STACK="${PROXY_FULL_STACK:-1}" ./start-proxy.sh)
fi

echo "[rebuild-proxy] done"
