#!/usr/bin/env bash
# Install the JobCome site into /root/local/nginx/conf/server/, test it, and reload nginx.
# Run as root, on any host that has nginx at /root/local/nginx — freshly built with
# build-nginx.sh or already there — and again whenever the site configuration changes.
#
#   sudo ./scripts/nginx/apply-nginx-conf.sh               # test, then reload (or start)
#   sudo ./scripts/nginx/apply-nginx-conf.sh --restart     # test, then stop and start
#   sudo ./scripts/nginx/apply-nginx-conf.sh --http-only   # no HTTPS site
#
# Writes only jc-upstreams.conf, jc-site-http.conf and jc-site-https.conf in conf/server/,
# plus the certificate in /root/local/nginx/ssl. Other sites on the same nginx, and its
# nginx.conf, are not touched. The change is all-or-nothing: if `nginx -t` rejects it, or
# nginx would not actually load the files, the previous files are put back and nginx is not
# reloaded, so a bad edit cannot take the other sites down with it.
#
# Env (optional; use `sudo -E` or `sudo VAR=value ...` so it reaches the script):
#   JC_NGINX_SERVER_NAME="jc.sspacee.com"  host names / IPv4 addresses, space or comma
#                                          separated. All go into server_name and the
#                                          certificate; the first is the primary.
#   JC_NGINX_HTTPS_PORT=443                HTTPS port. If another program owns it, HTTPS is
#                                          skipped with a warning, HTTP is unaffected.
#   JC_WEB_PORT=3000  JC_API_PORT=8000     upstream ports on this host
#   JC_NGINX_DEFAULT_SERVER=1              claim default_server on the site listeners.
#                                          Off by default: another site on this nginx
#                                          normally holds it, and two on one port make
#                                          `nginx -t` fail.
#   JC_NGINX_REGEN_CERT=1                  replace the self-signed certificate
#
# Certificate: self-signed and regenerated only when it does not cover every requested name,
# so a certificate a browser was told to trust survives repeated runs.
# Cookies: keep JC_COOKIE_SECURE=false while http:// stays a public address; a Secure cookie
# is never sent over http and the login would silently stop working there.
set -euo pipefail

LOG_TAG=apply-nginx
# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

# Commas are accepted as separators; the list is stored space separated.
SERVER_NAMES="$(printf '%s' "${JC_NGINX_SERVER_NAME:-jc.sspacee.com}" | tr ',' ' ' | xargs)"
SERVER_NAME="${SERVER_NAMES%% *}"
HTTPS_PORT="${JC_NGINX_HTTPS_PORT:-443}"
WEB_PORT="${JC_WEB_PORT:-3000}"
API_PORT="${JC_API_PORT:-8000}"

DO_RESTART=false
HTTP_ONLY=false
ENABLE_HTTPS=false
HTTP_LISTEN_FLAGS=""
HTTPS_LISTEN_FLAGS=""
HTTP2_ON_LINE=""
STAGE=""
BACKUP=""
TOUCHED=false

for arg in "$@"; do
  case "$arg" in
    --restart) DO_RESTART=true ;;
    --http-only) HTTP_ONLY=true ;;
    -h | --help)
      sed -n '2,31p' "$0"
      exit 0
      ;;
    *) die "unknown argument: $arg" ;;
  esac
done

# The names land in three syntaxes at once - a sed replacement, an nginx server_name and an
# openssl config - and none of them tolerates a stray `|`, `;`, quote or newline. Restricting
# them to host name characters here is cheaper than escaping correctly in each.
validate_input() {
  [[ -n "$SERVER_NAMES" ]] || die "JC_NGINX_SERVER_NAME is empty"
  local name
  for name in $SERVER_NAMES; do
    is_ipv4 "$name" && continue
    [[ "$name" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$ ]] \
      || die "invalid server name: '${name}' (host names or IPv4 addresses only)"
  done

  local port label
  for label in HTTPS_PORT WEB_PORT API_PORT; do
    port="${!label}"
    [[ "$port" =~ ^[0-9]{1,5}$ ]] || die "${label} must be a number, got '${port}'"
    port=$((10#$port))
    ((port >= 1 && port <= 65535)) || die "${label} out of range: ${port}"
    printf -v "$label" '%s' "$port"
  done
  ((HTTPS_PORT != 80)) || die "JC_NGINX_HTTPS_PORT cannot be 80, it serves the plain HTTP site"
  ((HTTPS_PORT != WEB_PORT && HTTPS_PORT != API_PORT)) \
    || die "JC_NGINX_HTTPS_PORT (${HTTPS_PORT}) collides with an upstream port"
}

# "https://host" on 443, "https://host:8443" otherwise.
https_origin() {
  if ((HTTPS_PORT == 443)); then printf 'https://%s' "$1"; else printf 'https://%s:%s' "$1" "$HTTPS_PORT"; fi
}

# Free for us when nothing listens there, or when the listener is this nginx (a reload).
# Anything else - a proxy, another web server - would make nginx fail to start altogether.
https_port_available() {
  command -v ss >/dev/null 2>&1 || {
    log "WARNING: 'ss' not found, cannot check whether port ${HTTPS_PORT} is free"
    return 0
  }
  local line owner
  line="$(ss -H -ltnp 2>/dev/null | awk -v port="$HTTPS_PORT" '$4 ~ (":" port "$")')"
  [[ -z "$line" ]] && return 0
  owner="$(printf '%s\n' "$line" | grep -o 'users:(("[^"]*"' | head -1 | sed -E 's/^users:\(\("//; s/"$//')"
  [[ "$owner" == "nginx" ]]
}

# `http2 on;` replaced the `http2` flag on `listen` in nginx 1.25.1; the old flag is
# deprecated from there on and the new directive does not exist before it.
compute_listen_flags() {
  local version default_flag=""
  version="$(nginx_version_number)"
  if ! nginx_has_http2; then
    # No HTTP/2 support compiled in: serve HTTPS over HTTP/1.1. Browsers do not mind.
    log "this nginx was built without --with-http_v2_module - HTTPS will use HTTP/1.1"
  elif ((version >= 1025001)); then
    HTTP2_ON_LINE="http2 on;"
  else
    HTTPS_LISTEN_FLAGS=" http2"
  fi
  case "${JC_NGINX_DEFAULT_SERVER:-0}" in
    1 | yes | true) default_flag=" default_server" ;;
    0 | no | false | "") ;;
    *) die "JC_NGINX_DEFAULT_SERVER must be 1 or 0, got '${JC_NGINX_DEFAULT_SERVER}'" ;;
  esac
  HTTP_LISTEN_FLAGS="$default_flag"
  HTTPS_LISTEN_FLAGS="${HTTPS_LISTEN_FLAGS}${default_flag}"
}

cert_wanted_entries() {
  local name
  for name in $SERVER_NAMES localhost 127.0.0.1; do
    if is_ipv4 "$name"; then printf 'IP Address:%s\n' "$name"; else printf 'DNS:%s\n' "$name"; fi
  done | sort -u
}

# True when the certificate already names everything we serve. Anything less - a certificate
# that predates a new domain, or one we cannot read - means regenerating, because nginx would
# otherwise serve a name the certificate does not carry.
cert_covers_names() {
  local have want
  have="$(openssl x509 -in "$1" -noout -ext subjectAltName 2>/dev/null \
    | tr ',' '\n' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' | grep -E '^(DNS|IP Address):' | sort -u)"
  [[ -n "$have" ]] || return 1
  want="$(cert_wanted_entries)"
  [[ -z "$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$have"))" ]]
}

ensure_certificate() {
  local cert="${SSL_DIR}/jc-selfsigned.crt" key="${SSL_DIR}/jc-selfsigned.key" cnf="${SSL_DIR}/openssl.cnf"
  mkdir -p "$SSL_DIR"

  if [[ -f "$cert" && -f "$key" && "${JC_NGINX_REGEN_CERT:-0}" != "1" ]]; then
    if cert_covers_names "$cert"; then
      log "keeping the existing certificate (covers: ${SERVER_NAMES})"
      return 0
    fi
    log "the existing certificate does not cover every requested name - regenerating"
  fi

  log "generating a self-signed certificate (10 years; ${SERVER_NAMES}, localhost, 127.0.0.1)"
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
    printf 'IP.%d = 127.0.0.1\n' "$((ip_index + 1))"
  } >"$cnf"

  openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout "$key" -out "$cert" -config "$cnf" -extensions v3_req >/dev/null 2>&1 \
    || die "openssl could not generate the certificate"
  chmod 600 "$key"
  chmod 644 "$cert"
}

# Files this script owns. The last two groups are earlier layouts: a combined jc-site.conf,
# and sites that used to live in conf.d. If one were still included next to the new files it
# would define the same upstreams or listener twice.
owned_files() {
  local f
  for f in "${SERVER_DIR}"/jc-*.conf "${CONF_DIR}"/conf.d/jc-*.conf; do
    [[ -e "$f" ]] && printf '%s\n' "$f"
  done
  return 0
}

backup_owned_files() {
  BACKUP="$(mktemp -d "${TMPDIR:-/tmp}/apply-nginx.XXXXXX")"
  local f rel
  while IFS= read -r f; do
    rel="${f#"${CONF_DIR}"/}"
    mkdir -p "${BACKUP}/$(dirname "$rel")"
    cp -p "$f" "${BACKUP}/${rel}"
  done < <(owned_files)
}

remove_owned_files() {
  local f
  while IFS= read -r f; do rm -f "$f"; done < <(owned_files)
}

restore_owned_files() {
  remove_owned_files
  [[ -n "$BACKUP" && -d "$BACKUP" ]] || return 0
  local f rel
  while IFS= read -r f; do
    rel="${f#"${BACKUP}"/}"
    mkdir -p "${CONF_DIR}/$(dirname "$rel")"
    cp -p "$f" "${CONF_DIR}/${rel}"
  done < <(find "$BACKUP" -type f)
}

cleanup() {
  local code=$?
  if [[ "$TOUCHED" == true && $code -ne 0 ]]; then
    log "failed - restoring the previous site files"
    restore_owned_files
  fi
  [[ -n "$STAGE" && -d "$STAGE" ]] && rm -rf "$STAGE"
  [[ -n "$BACKUP" && -d "$BACKUP" ]] && rm -rf "$BACKUP"
  return 0
}

stage_files() {
  STAGE="$(mktemp -d "${TMPDIR:-/tmp}/apply-nginx.XXXXXX")"
  render_template "${TEMPLATE_DIR}/jc-upstreams.conf" "${STAGE}/jc-upstreams.conf"
  render_template "${TEMPLATE_DIR}/jc-site-http.conf" "${STAGE}/jc-site-http.conf"
  if [[ "$ENABLE_HTTPS" == true ]]; then
    render_template "${TEMPLATE_DIR}/jc-site-https.conf" "${STAGE}/jc-site-https.conf"
  fi
  if grep -rq '__JC_' "$STAGE"; then
    die "an unreplaced placeholder is left in a rendered file: $(grep -rho '__JC_[A-Z0-9_]*__' "$STAGE" | sort -u | tr '\n' ' ')"
  fi
}

# The file must be one nginx really reads. `nginx -t` passes happily on a nginx.conf that
# does not include server/*.conf, so without this the site would be written, "tested" and
# silently inert. `nginx -T` lists every file it parsed as "# configuration file <path>:".
assert_site_loaded() {
  local expected dump line loaded found=false
  expected="$(realpath "${SERVER_DIR}/jc-site-http.conf" 2>/dev/null || echo "${SERVER_DIR}/jc-site-http.conf")"
  # The exit status is not used: `nginx -t` already accepted the file, and the only question
  # here is whether the site shows up in the dump.
  dump="$("$NGINX_BIN" -T -c "$MAIN_CONF" 2>&1 || true)"
  while IFS= read -r line; do
    loaded="${line#\# configuration file }"
    loaded="${loaded%:}"
    loaded="$(realpath "$loaded" 2>/dev/null || echo "$loaded")"
    if [[ "$loaded" == "$expected" ]]; then
      found=true
      break
    fi
  done < <(printf '%s\n' "$dump" | grep '^# configuration file ')
  [[ "$found" == true ]] || die "nginx would not load ${SERVER_DIR}/jc-site-http.conf.
       ${MAIN_CONF} does not include conf/server/*.conf. Either run build-nginx.sh (it rewrites
       a stock or generated nginx.conf), or add this line inside the http { } block by hand:
           include ${SERVER_DIR}/*.conf;"
}

nginx_apply() {
  if [[ "$DO_RESTART" == true ]]; then
    "$NGINX_BIN" -s stop -c "$MAIN_CONF" >/dev/null 2>&1 || true
    local waited=0
    while nginx_is_running && ((waited < 20)); do
      sleep 0.5
      waited=$((waited + 1))
    done
    log "starting nginx"
    "$NGINX_BIN" -c "$MAIN_CONF"
  elif "$NGINX_BIN" -s reload -c "$MAIN_CONF" >/dev/null 2>&1; then
    log "reloaded nginx"
  elif nginx_is_running; then
    die "nginx is running but refused the reload; the site files were kept. Try --restart."
  else
    log "nginx is not running - starting it"
    "$NGINX_BIN" -c "$MAIN_CONF"
  fi
}

# Non-fatal: the upstreams may simply not be started yet.
smoke_check() {
  command -v curl >/dev/null 2>&1 || return 0
  local code
  code="$(curl -s -o /dev/null -m 5 -H "Host: ${SERVER_NAME}" -w '%{http_code}' http://127.0.0.1/health 2>/dev/null || true)"
  case "$code" in
    200) log "check: http://${SERVER_NAME}/health answered 200 through nginx" ;;
    502 | 503 | 504) log "check: nginx answered ${code} - it cannot reach the API on 127.0.0.1:${API_PORT}; start backend.sh" ;;
    "" | 000) log "check: nothing answered on port 80 of this host" ;;
    *) log "check: /health answered ${code}" ;;
  esac
}

print_summary() {
  local name
  log "done. Site files: ${SERVER_DIR}/jc-*.conf"
  for name in $SERVER_NAMES; do log "  http://${name}/"; done
  if [[ "$ENABLE_HTTPS" == true ]]; then
    for name in $SERVER_NAMES; do log "  $(https_origin "$name")/   (self-signed: browsers warn)"; done
    ((HTTPS_PORT == 443)) || log "  open TCP ${HTTPS_PORT} in the cloud security group, or HTTPS times out from outside"
  else
    log "  HTTPS skipped"
  fi
  log "upstreams: web 127.0.0.1:${WEB_PORT}, api 127.0.0.1:${API_PORT} (frontend.sh / backend.sh)"
}

main() {
  require_root
  validate_input
  [[ -x "$NGINX_BIN" ]] || die "no nginx at ${NGINX_BIN} - run build-nginx.sh first"
  [[ -d "$TEMPLATE_DIR" ]] || die "missing templates: ${TEMPLATE_DIR}"
  [[ -f "$MAIN_CONF" ]] || die "missing ${MAIN_CONF} - run build-nginx.sh first"
  mkdir -p "$SERVER_DIR"

  if [[ "$HTTP_ONLY" == true ]]; then
    log "--http-only: no HTTPS site"
  elif https_port_available; then
    ENABLE_HTTPS=true
  else
    log "WARNING: port ${HTTPS_PORT} is in use by another program - skipping HTTPS."
    log "         Set JC_NGINX_HTTPS_PORT to a free port to enable it."
  fi

  compute_listen_flags
  trap cleanup EXIT
  stage_files
  [[ "$ENABLE_HTTPS" == true ]] && ensure_certificate

  backup_owned_files
  TOUCHED=true
  remove_owned_files
  cp "${STAGE}"/jc-*.conf "$SERVER_DIR"/
  log "wrote $(cd "$STAGE" && ls jc-*.conf | tr '\n' ' ')to ${SERVER_DIR}"

  "$NGINX_BIN" -t -c "$MAIN_CONF" || die "nginx -t rejected the configuration"
  assert_site_loaded
  TOUCHED=false

  nginx_apply
  smoke_check
  print_summary
}

main "$@"
