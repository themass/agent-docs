#!/usr/bin/env bash
# Build/install Nginx under /root/local (symlink /root/local/nginx), sources in /root/soft,
# generate a self-signed TLS cert, and install JobCome reverse-proxy config (HTTP + HTTPS).
#
# Run on the **application server** as root, after job-come API/Web are listening on
# 127.0.0.1:8000 and :3000 (./scripts/backend.sh start && ./scripts/frontend.sh start).
#
# Usage (from job-come repo on the server):
#   sudo ./scripts/nginx/install-jc-nginx.sh              # full install
#   sudo ./scripts/nginx/install-jc-nginx.sh --config-only # refresh conf + cert, reload
#   sudo ./scripts/nginx/install-jc-nginx.sh --reload
#   sudo ./scripts/nginx/install-jc-nginx.sh --stop
#
# Env (optional):
#   JC_NGINX_VERSION=1.26.3
#   JC_NGINX_SERVER_NAME=jc.sspacee.com    # also used in self-signed SAN
#   JC_WEB_PORT=3000  JC_API_PORT=8000
#   JC_NGINX_INSTALL_ROOT=/root/local
#   JC_NGINX_SOFT_ROOT=/root/soft
#   JC_NGINX_FORCE_REBUILD=1             # recompile even if prefix exists
#   JC_NGINX_REGEN_CERT=1                # replace self-signed cert
#
# Cookie / public URL (backend + frontend build) must match how users open the site:
#   http://...  → JC_PUBLIC_URL=http://..., JC_COOKIE_SECURE=false
#   https://... → JC_PUBLIC_URL=https://..., JC_COOKIE_SECURE=true (browser will warn on self-signed)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"

NGINX_VERSION="${JC_NGINX_VERSION:-1.26.3}"
SERVER_NAME="${JC_NGINX_SERVER_NAME:-jc.sspacee.com}"
WEB_PORT="${JC_WEB_PORT:-3000}"
API_PORT="${JC_API_PORT:-8000}"
INSTALL_ROOT="${JC_NGINX_INSTALL_ROOT:-/root/local}"
SOFT_ROOT="${JC_NGINX_SOFT_ROOT:-/root/soft}"

PREFIX="${INSTALL_ROOT}/nginx-${NGINX_VERSION}"
NGINX_LINK="${INSTALL_ROOT}/nginx"
NGINX_BIN="${NGINX_LINK}/sbin/nginx"
CONF_DIR="${NGINX_LINK}/conf"
CONF_D="${CONF_DIR}/conf.d"
SSL_DIR="${NGINX_LINK}/ssl"
LOG_DIR="${NGINX_LINK}/logs"

TARBALL="nginx-${NGINX_VERSION}.tar.gz"
DOWNLOAD_URL="https://nginx.org/download/${TARBALL}"
BUILD_DIR="${SOFT_ROOT}/nginx-${NGINX_VERSION}-build"
EXTRACT_DIR="${SOFT_ROOT}/nginx-${NGINX_VERSION}"

CONFIG_ONLY=false
DO_RELOAD=false
DO_STOP=false

for arg in "$@"; do
  case "$arg" in
    --config-only) CONFIG_ONLY=true ;;
    --reload) DO_RELOAD=true ;;
    --stop) DO_STOP=true ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

log() { printf '[jc-nginx] %s\n' "$*"; }
die() { printf '[jc-nginx] ERROR: %s\n' "$*" >&2; exit 1; }

require_root() {
  [[ "$(id -u)" -eq 0 ]] || die "run as root (sudo $0)"
}

install_build_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    log "installing build dependencies (apt)"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      build-essential wget tar ca-certificates \
      libpcre3-dev zlib1g-dev libssl-dev openssl
  elif command -v dnf >/dev/null 2>&1; then
    log "installing build dependencies (dnf)"
    dnf install -y gcc make wget tar ca-certificates \
      pcre-devel zlib-devel openssl-devel openssl
  elif command -v yum >/dev/null 2>&1; then
    log "installing build dependencies (yum)"
    yum install -y gcc make wget tar ca-certificates \
      pcre-devel zlib-devel openssl-devel openssl
  else
    die "unsupported OS: need apt-get, dnf, or yum"
  fi
}

compile_nginx() {
  if [[ -x "${PREFIX}/sbin/nginx" && "${JC_NGINX_FORCE_REBUILD:-0}" != "1" ]]; then
    log "nginx already installed at ${PREFIX} (set JC_NGINX_FORCE_REBUILD=1 to rebuild)"
    return 0
  fi

  install_build_deps
  mkdir -p "$SOFT_ROOT"
  cd "$SOFT_ROOT"

  if [[ ! -f "${SOFT_ROOT}/${TARBALL}" ]]; then
    log "downloading ${DOWNLOAD_URL}"
    wget -q --show-progress -O "${TARBALL}" "${DOWNLOAD_URL}"
  fi

  rm -rf "$EXTRACT_DIR" "$BUILD_DIR"
  tar -xzf "${TARBALL}"
  # The nginx.org tarball extracts into "nginx-${NGINX_VERSION}/" directly, which
  # is already what EXTRACT_DIR names — moving it onto itself used to fail here
  # ("mv: cannot move 'nginx-1.26.3' to a subdirectory of itself") on every run.
  mkdir -p "$BUILD_DIR"

  log "configuring nginx → prefix ${PREFIX}"
  cd "$BUILD_DIR"
  "${EXTRACT_DIR}/configure" \
    --prefix="${PREFIX}" \
    --sbin-path="${PREFIX}/sbin/nginx" \
    --conf-path="${PREFIX}/conf/nginx.conf" \
    --error-log-path="${PREFIX}/logs/error.log" \
    --http-log-path="${PREFIX}/logs/access.log" \
    --pid-path="${PREFIX}/logs/nginx.pid" \
    --lock-path="${PREFIX}/logs/nginx.lock" \
    --with-http_ssl_module \
    --with-http_v2_module \
    --with-http_realip_module \
    --with-stream \
    --with-threads

  log "compiling nginx (this may take a few minutes)"
  make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"
  make install

  [[ -x "${PREFIX}/sbin/nginx" ]] || die "install failed: missing ${PREFIX}/sbin/nginx"
  log "installed nginx $("${PREFIX}/sbin/nginx" -v 2>&1)"
}

link_nginx() {
  mkdir -p "$INSTALL_ROOT"
  ln -sfn "$PREFIX" "$NGINX_LINK"
  log "symlink ${NGINX_LINK} → ${PREFIX}"
}

render_template() {
  local src="$1" dest="$2"
  sed \
    -e "s|__JC_NGINX_CONF__|${CONF_DIR}|g" \
    -e "s|__JC_NGINX_LOGS__|${LOG_DIR}|g" \
    -e "s|__JC_SSL_DIR__|${SSL_DIR}|g" \
    -e "s|__JC_SERVER_NAME__|${SERVER_NAME}|g" \
    -e "s|__JC_WEB_PORT__|${WEB_PORT}|g" \
    -e "s|__JC_API_PORT__|${API_PORT}|g" \
    "$src" >"$dest"
}

install_config() {
  [[ -d "$TEMPLATE_DIR" ]] || die "missing templates: ${TEMPLATE_DIR}"
  mkdir -p "$CONF_D" "$SSL_DIR" "$LOG_DIR"

  render_template "${TEMPLATE_DIR}/nginx.conf" "${CONF_DIR}/nginx.conf"
  render_template "${TEMPLATE_DIR}/jc-site.conf" "${CONF_D}/jc-site.conf"
  log "wrote ${CONF_DIR}/nginx.conf and ${CONF_D}/jc-site.conf"
}

generate_self_signed_cert() {
  local cert="${SSL_DIR}/jc-selfsigned.crt"
  local key="${SSL_DIR}/jc-selfsigned.key"
  local cnf="${SSL_DIR}/openssl.cnf"

  if [[ -f "$cert" && -f "$key" && "${JC_NGINX_REGEN_CERT:-0}" != "1" ]]; then
    log "keeping existing self-signed cert in ${SSL_DIR}"
    return 0
  fi

  log "generating self-signed certificate (10 years, SAN: ${SERVER_NAME}, localhost, 127.0.0.1)"
  cat >"$cnf" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = ${SERVER_NAME}

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${SERVER_NAME}
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$key" -out "$cert" -config "$cnf" -extensions v3_req
  chmod 600 "$key"
  chmod 644 "$cert"
  log "certificate: ${cert}"
}

nginx_test() {
  "$NGINX_BIN" -t -c "${CONF_DIR}/nginx.conf"
}

nginx_start_or_reload() {
  if [[ -f "${LOG_DIR}/nginx.pid" ]] && kill -0 "$(cat "${LOG_DIR}/nginx.pid")" 2>/dev/null; then
    log "reloading nginx"
    "$NGINX_BIN" -s reload -c "${CONF_DIR}/nginx.conf"
  else
    log "starting nginx"
    "$NGINX_BIN" -c "${CONF_DIR}/nginx.conf"
  fi
}

nginx_stop() {
  if [[ -f "${LOG_DIR}/nginx.pid" ]]; then
    "$NGINX_BIN" -s stop -c "${CONF_DIR}/nginx.conf" 2>/dev/null || true
    log "stopped nginx"
  else
    log "nginx not running (no pid file)"
  fi
}

print_summary() {
  cat <<EOF

[jc-nginx] Done.
  Binary:   ${NGINX_BIN}
  Config:   ${CONF_DIR}/nginx.conf
  Site:     ${CONF_D}/jc-site.conf
  TLS:      ${SSL_DIR}/jc-selfsigned.{crt,key}
  Logs:     ${LOG_DIR}/

  HTTP:  http://${SERVER_NAME}/          (also http://<server-ip>/ if DNS points here)
  HTTPS: https://${SERVER_NAME}/        (browser will warn — self-signed)

  Upstream (must be running on this host):
    Web 127.0.0.1:${WEB_PORT}   → ./scripts/frontend.sh start
    API 127.0.0.1:${API_PORT}   → ./scripts/backend.sh start

  Align job-come env with the URL users use:
    http only  → JC_PUBLIC_URL=http://${SERVER_NAME}  JC_COOKIE_SECURE=false
    https      → JC_PUBLIC_URL=https://${SERVER_NAME} JC_COOKIE_SECURE=true
    frontend   → NEXT_PUBLIC_SITE_URL same scheme, then npm run build

  Reload after template changes: sudo $0 --config-only
EOF
}

main() {
  require_root

  if [[ "$DO_STOP" == true ]]; then
    [[ -x "$NGINX_BIN" ]] || die "nginx not installed at ${NGINX_LINK}"
    nginx_stop
    exit 0
  fi

  if [[ "$DO_RELOAD" == true ]]; then
    [[ -x "$NGINX_BIN" ]] || die "nginx not installed — run without --reload first"
    nginx_test
    nginx_start_or_reload
    exit 0
  fi

  if [[ "$CONFIG_ONLY" == false ]]; then
    compile_nginx
    link_nginx
  else
    [[ -L "$NGINX_LINK" || -d "$NGINX_LINK" ]] || die "nginx not installed — run full install first"
    [[ -x "$NGINX_BIN" ]] || die "missing ${NGINX_BIN}"
  fi

  install_config
  generate_self_signed_cert
  nginx_test
  nginx_start_or_reload
  print_summary
}

main "$@"
