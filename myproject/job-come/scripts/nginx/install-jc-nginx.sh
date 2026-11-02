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
#   sudo ./scripts/nginx/install-jc-nginx.sh --http-only   # never attempt :443, even if free
#   sudo ./scripts/nginx/install-jc-nginx.sh --reload
#   sudo ./scripts/nginx/install-jc-nginx.sh --stop
#
# Env (optional):
#   JC_NGINX_VERSION=1.26.3
#   JC_NGINX_SERVER_NAME="jc.sspacee.com"  # one or more host names/IPs, space or comma
#                                          # separated; all go into nginx server_name and
#                                          # the certificate SAN. The first is the primary.
#   JC_NGINX_HTTPS_PORT=443                # port for the HTTPS site (see below)
#   JC_WEB_PORT=3000  JC_API_PORT=8000
#   JC_NGINX_INSTALL_ROOT=/root/local
#   JC_NGINX_SOFT_ROOT=/root/soft
#   JC_NGINX_FORCE_REBUILD=1             # recompile even if prefix exists
#   JC_NGINX_REGEN_CERT=1                # replace self-signed cert unconditionally
#
# Adding a domain:
#   JC_NGINX_SERVER_NAME="jc.sspacee.com jc2.example.com" sudo -E ./scripts/nginx/install-jc-nginx.sh --config-only
# The certificate is regenerated automatically whenever a requested name is not already
# in its SAN, so a new domain never ends up served with a certificate that names only the
# old one. A certificate that already covers every requested name is left alone, so a
# browser exception or an imported trust anchor keeps working across runs.
#
# Port 443: if something else already owns it (checked with `ss`; a prior run of
# this same nginx does not count), HTTPS is skipped automatically with a warning
# instead of failing nginx's startup entirely — binding the HTTPS port is one `listen`
# directive among several, and nginx refuses to start AT ALL if any of them
# fails, which would otherwise take the working HTTP site down over an
# unrelated port conflict. Use --http-only to skip it unconditionally. To serve HTTPS
# next to a program that owns 443, set JC_NGINX_HTTPS_PORT to a free port (for example
# 8443); that port must also be opened in the cloud security group, and URLs then need
# the port (https://host:8443/).
#
# Cookie / public URL (backend + frontend build) must match how users open the site:
#   http://...  → JC_PUBLIC_URL=http://..., JC_COOKIE_SECURE=false
#   https://... → JC_PUBLIC_URL=https://..., JC_COOKIE_SECURE=true (browser will warn on self-signed)
# While HTTP stays the main address, keep JC_COOKIE_SECURE=false: a Secure cookie is never
# sent over http, so the login would silently stop working there.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"

NGINX_VERSION="${JC_NGINX_VERSION:-1.26.3}"
# Commas are accepted as separators too; the list is stored space separated.
SERVER_NAMES="$(printf '%s' "${JC_NGINX_SERVER_NAME:-jc.sspacee.com}" | tr ',' ' ' | xargs)"
SERVER_NAME="${SERVER_NAMES%% *}"
HTTPS_PORT="${JC_NGINX_HTTPS_PORT:-443}"
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
EXTRACT_DIR="${SOFT_ROOT}/nginx-${NGINX_VERSION}"

CONFIG_ONLY=false
DO_RELOAD=false
DO_STOP=false
FORCE_HTTP_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --config-only) CONFIG_ONLY=true ;;
    --http-only) FORCE_HTTP_ONLY=true ;;
    --reload) DO_RELOAD=true ;;
    --stop) DO_STOP=true ;;
    -h|--help) sed -n '2,48p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

log() { printf '[jc-nginx] %s\n' "$*"; }
die() { printf '[jc-nginx] ERROR: %s\n' "$*" >&2; exit 1; }

require_root() {
  [[ "$(id -u)" -eq 0 ]] || die "run as root (sudo $0)"
}

is_ipv4() {
  [[ "$1" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]
}

# The names land in three syntaxes at once — a sed replacement, an nginx `server_name`
# and an openssl config — and none of them tolerates a stray `|`, `;`, quote or newline.
# Restricting to hostname characters here is cheaper than escaping correctly in each.
validate_names_and_ports() {
  [[ -n "$SERVER_NAMES" ]] || die "JC_NGINX_SERVER_NAME is empty"
  local name
  for name in $SERVER_NAMES; do
    if is_ipv4 "$name"; then
      continue
    fi
    [[ "$name" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$ ]] \
      || die "invalid server name: '${name}' (use host names or IPv4 addresses only)"
  done

  # `10#` so a value like 0443 is read as decimal, not rejected or read as octal.
  [[ "$HTTPS_PORT" =~ ^[0-9]{1,5}$ ]] || die "JC_NGINX_HTTPS_PORT must be a number, got '${HTTPS_PORT}'"
  HTTPS_PORT=$((10#$HTTPS_PORT))
  (( HTTPS_PORT >= 1 && HTTPS_PORT <= 65535 )) || die "JC_NGINX_HTTPS_PORT out of range: ${HTTPS_PORT}"
  (( HTTPS_PORT != 80 )) || die "JC_NGINX_HTTPS_PORT cannot be 80, it serves the plain HTTP site"
  (( HTTPS_PORT != WEB_PORT && HTTPS_PORT != API_PORT )) \
    || die "JC_NGINX_HTTPS_PORT (${HTTPS_PORT}) collides with the web/API upstream port"
}

# "https://host" for the default port, "https://host:8443" otherwise.
https_origin() {
  if (( HTTPS_PORT == 443 )); then
    printf 'https://%s' "$1"
  else
    printf 'https://%s:%s' "$1" "$HTTPS_PORT"
  fi
}

# True (0) when :443 is free for us to bind — nothing listening, or the only
# listener is our own already-running nginx (a reload, not a conflict). False
# when some other process owns it, e.g. a proxy service unrelated to this
# deploy; attempting to bind there would fail nginx's startup entirely.
https_port_available() {
  local line owner
  line="$(ss -H -ltnp 2>/dev/null | awk -v port="$HTTPS_PORT" '$4 ~ (":" port "$")')"
  [[ -z "$line" ]] && return 0
  owner="$(printf '%s\n' "$line" | grep -o 'users:(("[^"]*"' | head -1 | sed -E 's/^users:\(\("//; s/"$//')"
  [[ "$owner" == "nginx" ]]
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

  rm -rf "$EXTRACT_DIR"
  tar -xzf "${TARBALL}"
  # The nginx.org tarball extracts into "nginx-${NGINX_VERSION}/" directly, which
  # is already what EXTRACT_DIR names — moving it onto itself used to fail here
  # ("mv: cannot move 'nginx-1.26.3' to a subdirectory of itself") on every run.

  log "configuring nginx → prefix ${PREFIX}"
  # nginx's `configure` is not autoconf-generated: it sources `auto/options` etc.
  # relative to the current directory, not relative to the script's own path, so
  # it only works run as `./configure` from inside the extracted source tree — an
  # out-of-tree build (cd elsewhere, invoke configure by absolute/relative path)
  # fails immediately with ".: Can't open auto/options", before any compilation.
  cd "$EXTRACT_DIR"
  ./configure \
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
    -e "s|__JC_SERVER_NAME__|${SERVER_NAMES}|g" \
    -e "s|__JC_HTTPS_PORT__|${HTTPS_PORT}|g" \
    -e "s|__JC_WEB_PORT__|${WEB_PORT}|g" \
    -e "s|__JC_API_PORT__|${API_PORT}|g" \
    "$src" >"$dest"
}

install_config() {
  [[ -d "$TEMPLATE_DIR" ]] || die "missing templates: ${TEMPLATE_DIR}"
  mkdir -p "$CONF_D" "$SSL_DIR" "$LOG_DIR"

  # Pre-split-layout leftover: a combined jc-site.conf from before this script
  # separated HTTP/HTTPS into their own files would duplicate the `upstream`
  # blocks now in jc-upstreams.conf and make nginx refuse to start.
  rm -f "${CONF_D}/jc-site.conf"

  render_template "${TEMPLATE_DIR}/nginx.conf" "${CONF_DIR}/nginx.conf"
  render_template "${TEMPLATE_DIR}/jc-upstreams.conf" "${CONF_D}/jc-upstreams.conf"
  render_template "${TEMPLATE_DIR}/jc-site-http.conf" "${CONF_D}/jc-site-http.conf"
  log "wrote ${CONF_DIR}/nginx.conf, jc-upstreams.conf, jc-site-http.conf"

  if [[ "$ENABLE_HTTPS" == true ]]; then
    render_template "${TEMPLATE_DIR}/jc-site-https.conf" "${CONF_D}/jc-site-https.conf"
    log "wrote jc-site-https.conf"
  else
    # Remove a previous run's https conf — leaving it would make nginx try (and
    # fail) to bind :443 again even though this run decided to skip it.
    rm -f "${CONF_D}/jc-site-https.conf"
  fi
}

# Every name the site is reachable by, plus loopback, as `DNS:` / `IP Address:` entries.
cert_wanted_entries() {
  local name
  for name in $SERVER_NAMES localhost 127.0.0.1; do
    if is_ipv4 "$name"; then
      printf 'IP Address:%s\n' "$name"
    else
      printf 'DNS:%s\n' "$name"
    fi
  done | sort -u
}

# True when the existing certificate already names everything we want to serve. Anything
# less — an older certificate that predates a newly added domain, or one we cannot read —
# means regenerating, because nginx would otherwise serve a name the certificate does not
# carry and every browser would report a name mismatch on top of the self-signed warning.
cert_covers_names() {
  local cert="$1" have want
  have="$(openssl x509 -in "$cert" -noout -ext subjectAltName 2>/dev/null \
    | tr ',' '\n' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' | grep -E '^(DNS|IP Address):' | sort -u)"
  [[ -n "$have" ]] || return 1
  want="$(cert_wanted_entries)"
  [[ -z "$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$have"))" ]]
}

generate_self_signed_cert() {
  [[ "$ENABLE_HTTPS" == true ]] || return 0
  local cert="${SSL_DIR}/jc-selfsigned.crt"
  local key="${SSL_DIR}/jc-selfsigned.key"
  local cnf="${SSL_DIR}/openssl.cnf"

  if [[ -f "$cert" && -f "$key" && "${JC_NGINX_REGEN_CERT:-0}" != "1" ]]; then
    if cert_covers_names "$cert"; then
      log "keeping existing self-signed cert in ${SSL_DIR} (already covers: ${SERVER_NAMES})"
      return 0
    fi
    log "existing certificate does not cover every requested name — regenerating"
  fi

  log "generating self-signed certificate (10 years, names: ${SERVER_NAMES}, localhost, 127.0.0.1)"
  {
    cat <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = ${SERVER_NAME}

[v3_req]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
EOF
    local dns_index=0 ip_index=0 name
    for name in $SERVER_NAMES localhost; do
      if is_ipv4 "$name"; then
        ip_index=$((ip_index + 1))
        printf 'IP.%d = %s\n' "$ip_index" "$name"
      else
        dns_index=$((dns_index + 1))
        printf 'DNS.%d = %s\n' "$dns_index" "$name"
      fi
    done
    ip_index=$((ip_index + 1))
    printf 'IP.%d = 127.0.0.1\n' "$ip_index"
  } >"$cnf"

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
  local name http_lines="" https_lines="" security_group=""
  for name in $SERVER_NAMES; do
    http_lines+="    http://${name}/"$'\n'
  done
  if [[ "$ENABLE_HTTPS" == true ]]; then
    for name in $SERVER_NAMES; do
      https_lines+="    $(https_origin "$name")/"$'\n'
    done
    https_lines+="    (self-signed: browsers show a warning until the certificate is trusted)"
    if (( HTTPS_PORT != 443 )); then
      security_group="
  Open TCP ${HTTPS_PORT} in the cloud security group / firewall, or HTTPS will time out from outside."
    fi
  else
    https_lines="    skipped — port ${HTTPS_PORT} is already in use by another process on this host.
    Set JC_NGINX_HTTPS_PORT to a free port (e.g. 8443), or free the port, then re-run with
    --config-only; nginx does not need to be rebuilt."
  fi
  cat <<EOF

[jc-nginx] Done.
  Binary:   ${NGINX_BIN}
  Config:   ${CONF_DIR}/nginx.conf
  Site:     ${CONF_D}/jc-site-http.conf$([[ "$ENABLE_HTTPS" == true ]] && echo ", jc-site-https.conf")
  TLS:      ${SSL_DIR}/jc-selfsigned.{crt,key}
  Logs:     ${LOG_DIR}/

  HTTP:
${http_lines%$'\n'}
  HTTPS:
${https_lines}${security_group}

  Upstream (must be running on this host):
    Web 127.0.0.1:${WEB_PORT}   → ./scripts/frontend.sh start
    API 127.0.0.1:${API_PORT}   → ./scripts/backend.sh start

  Align job-come env with the URL users use:
    http is the main address  → JC_PUBLIC_URL=http://${SERVER_NAME}  JC_COOKIE_SECURE=false
    https is the main address → JC_PUBLIC_URL=$(https_origin "$SERVER_NAME") JC_COOKIE_SECURE=true
    frontend                  → NEXT_PUBLIC_SITE_URL same scheme, then rebuild the frontend
  With both addresses live, keep JC_COOKIE_SECURE=false so the login works on either.

  Reload after template changes: sudo $0 --config-only
EOF
}

main() {
  require_root
  validate_names_and_ports

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

  if [[ "$FORCE_HTTP_ONLY" == true ]]; then
    ENABLE_HTTPS=false
    log "--http-only: skipping HTTPS unconditionally"
  elif https_port_available; then
    ENABLE_HTTPS=true
  else
    ENABLE_HTTPS=false
    log "WARNING: port ${HTTPS_PORT} is already in use by another process on this host — skipping HTTPS."
    log "         The site will serve HTTP only. Set JC_NGINX_HTTPS_PORT to a free port to enable it."
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

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
