#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
tag="${1:?usage: rollback.sh <previous-immutable-image-tag>}"
: "${KUBE_NAMESPACE:=poetry-agent-staging}"
kubectl -n "$KUBE_NAMESPACE" set image deployment/poetry-agent-bff agent-bff="poetry/agent-bff:${tag}"
kubectl -n "$KUBE_NAMESPACE" set image deployment/poetry-domain-mcp poetry-domain-mcp="poetry/poetry-domain-mcp:${tag}"
printf 'Rollback initiated to immutable tag %s\n' "$tag"
