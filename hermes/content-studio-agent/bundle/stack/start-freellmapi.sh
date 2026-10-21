#!/usr/bin/env bash
# Start FreeLLMAPI server (Docker). npm package "freellmapi" is CLI-only — not the router.
set -euo pipefail

FREELLMAPI_PORT="${FREELLMAPI_PORT:-3011}"
FREELLMAPI_URL="${FREELLMAPI_URL:-http://127.0.0.1:${FREELLMAPI_PORT}}"
RUNTIME_DIR="${RUNTIME_DIR:?RUNTIME_DIR required}"
LOGS_DIR="${LOGS_DIR:-$RUNTIME_DIR/logs}"
# Docker compose + .env live here (not the empty runtime/freellmapi-data stub).
FREELLMAPI_INSTALL_DIR="${FREELLMAPI_INSTALL_DIR:-$HOME/freellmapi}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
FREELLMAPI_IMAGE="${FREELLMAPI_IMAGE:-ghcr.io/tashfeenahmed/freellmapi:latest}"

log() { printf '\033[1;36m[freellmapi]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[freellmapi]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[freellmapi]\033[0m %s\n' "$*" >&2; }

mkdir -p "$LOGS_DIR" "$FREELLMAPI_INSTALL_DIR"

read_api_key() {
  local secrets="${HERMES_HOME}/secrets.env" k
  [[ -f "$secrets" ]] || return 1
  k="$(grep -E '^LLM_API_KEY=' "$secrets" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "'\''')"
  [[ -n "$k" && "$k" != sk-your-key-here && "$k" != sk-mem-* ]] || return 1
  printf '%s' "$k"
}

http_models_ok() {
  local key="${1:-}" code
  local hdr=(-H "Authorization: Bearer ${key}")
  [[ -n "$key" ]] || hdr=()
  code="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "${FREELLMAPI_URL}/v1/models" "${hdr[@]}" 2>/dev/null || echo 000)"
  [[ "$code" =~ ^(200|401)$ ]]
}

if http_models_ok "$(read_api_key || true)"; then
  log "Already up: ${FREELLMAPI_URL}"
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  err "FreeLLMAPI server needs Docker (npm freellmapi is setup-CLI only)."
  err "Install: curl -fsSL https://freellmapi.co/install.sh | bash  (or FreeLLMAPI Desktop from GitHub Releases)"
  err "Then set PORT=${FREELLMAPI_PORT} in ~/freellmapi/.env and re-run the stack."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  err "Docker is installed but not running — start Docker Desktop, then re-run the stack."
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  err "Docker Compose required for FreeLLMAPI"
  exit 1
fi

mkdir -p "$FREELLMAPI_INSTALL_DIR"
cd "$FREELLMAPI_INSTALL_DIR"

if [[ ! -f .env ]]; then
  if command -v openssl >/dev/null 2>&1; then
    KEY="$(openssl rand -hex 32)"
  else
    KEY="$(od -vN 32 -An -tx1 /dev/urandom | tr -d ' \n')"
  fi
  umask 077
  cat > .env <<EOF
ENCRYPTION_KEY=$KEY
PORT=$FREELLMAPI_PORT
HOST_BIND=127.0.0.1
EOF
  umask 022
  log "Created ${FREELLMAPI_INSTALL_DIR}/.env (encryption key for provider keys)"
else
  if grep -q '^PORT=' .env 2>/dev/null; then
    sed -i '' "s/^PORT=.*/PORT=${FREELLMAPI_PORT}/" .env 2>/dev/null || sed -i "s/^PORT=.*/PORT=${FREELLMAPI_PORT}/" .env
  else
    printf '\nPORT=%s\n' "$FREELLMAPI_PORT" >> .env
  fi
fi

cat > docker-compose.yml <<EOF
services:
  freellmapi:
    image: ${FREELLMAPI_IMAGE}
    env_file:
      - .env
    environment:
      NODE_ENV: production
      PORT: 3001
    ports:
      - "\${HOST_BIND:-127.0.0.1}:\${PORT:-${FREELLMAPI_PORT}}:3001"
    volumes:
      - freellmapi-data:/app/server/data
    restart: unless-stopped

volumes:
  freellmapi-data:
EOF

log "Pulling ${FREELLMAPI_IMAGE} (first run may take several minutes)..."
"${COMPOSE[@]}" pull 2>&1 | while IFS= read -r line; do log "  ${line}"; done
log "Starting FreeLLMAPI on ${FREELLMAPI_URL} (data volume in Docker; config ${FREELLMAPI_INSTALL_DIR})"
"${COMPOSE[@]}" up -d

for i in $(seq 1 90); do
  if http_models_ok "$(read_api_key || true)"; then
    log "FreeLLMAPI ready — open ${FREELLMAPI_URL} → Keys, then set secrets.env LLM_API_KEY to freellmapi-..."
    exit 0
  fi
  if (( i % 5 == 0 )); then
    log "Waiting for FreeLLMAPI on ${FREELLMAPI_URL}... (${i}/90)"
  fi
  sleep 2
done

err "FreeLLMAPI did not respond on ${FREELLMAPI_URL}/v1/models — check: cd ${FREELLMAPI_INSTALL_DIR} && ${COMPOSE[*]} logs"
exit 1
