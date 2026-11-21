#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
cd "$CONTENT_AGENT"
tag="${1:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
for service in agent-bff poetry-domain-mcp agent-worker; do
  docker build -f "agent/${service}/Dockerfile" -t "poetry/${service}:${tag}" .
done
printf 'Built images with tag: %s\n' "$tag"
