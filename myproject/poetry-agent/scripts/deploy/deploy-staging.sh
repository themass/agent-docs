#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
tag="${1:?usage: deploy-staging.sh <immutable-image-tag>}"
: "${STAGING_ENV_FILE:?set STAGING_ENV_FILE to the staging environment file}"
# The platform deployer supplies image registry, secrets and namespace. This script only validates
# the committed profile before applying manifests; no schema migration is hidden in an app deploy.
python3 "$CONTENT_PIPELINE/tools/dev/check_profile.py"
sed "s/\${IMAGE_TAG}/${tag}/g" "$CONTENT_DEPLOY/k8s/staging.yaml" | kubectl apply -f -
printf 'Applied staging manifests for immutable tag %s\n' "$tag"
