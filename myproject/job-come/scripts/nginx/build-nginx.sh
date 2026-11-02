#!/usr/bin/env bash
# Build and install nginx on a host that has none. Run as root, once per machine.
#
#   sudo ./scripts/nginx/build-nginx.sh            # install if missing, otherwise do nothing
#   sudo ./scripts/nginx/build-nginx.sh --force    # rebuild the same version in place
#
# The result is identical on every host:
#   /root/local/nginx            symlink to /root/local/nginx-<version>
#   /root/local/nginx/conf/nginx.conf       includes conf/server/*.conf
#   /root/local/nginx/conf/server/          one file per site (apply-nginx-conf.sh writes ours)
#   /root/local/nginx/ssl, /logs
# Sources are unpacked under /root/soft.
#
# This script never writes a site. Run apply-nginx-conf.sh next, and again whenever the
# site configuration changes.
#
# A host that already has nginx at /root/local/nginx is left alone: no rebuild, no relink,
# and nginx.conf is rewritten only if it is the stock file or one this tooling wrote. A
# nginx.conf somebody maintains by hand is never touched; if it lacks the include line the
# script prints the line to add.
#
# Env (optional):
#   JC_NGINX_VERSION=1.26.3
#   JC_NGINX_URL=<tarball url>      default https://nginx.org/download/nginx-<version>.tar.gz
#   JC_NGINX_MAKE_JOBS=2            compiler parallelism; small hosts run out of memory above this
set -euo pipefail

LOG_TAG=build-nginx
# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

NGINX_VERSION="${JC_NGINX_VERSION:-1.26.3}"
PREFIX="${INSTALL_ROOT}/nginx-${NGINX_VERSION}"
TARBALL="nginx-${NGINX_VERSION}.tar.gz"
DOWNLOAD_URL="${JC_NGINX_URL:-https://nginx.org/download/${TARBALL}}"
EXTRACT_DIR="${SOFT_ROOT}/nginx-${NGINX_VERSION}"
MAKE_JOBS="${JC_NGINX_MAKE_JOBS:-2}"
FORCE=false

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    -h | --help)
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *) die "unknown argument: $arg" ;;
  esac
done

install_build_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    log "installing build dependencies (apt)"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      build-essential wget tar gzip ca-certificates libpcre3-dev zlib1g-dev libssl-dev openssl
  elif command -v dnf >/dev/null 2>&1; then
    log "installing build dependencies (dnf)"
    dnf install -y gcc make wget tar gzip ca-certificates pcre-devel zlib-devel openssl-devel openssl
  elif command -v yum >/dev/null 2>&1; then
    log "installing build dependencies (yum)"
    yum install -y gcc make wget tar gzip ca-certificates pcre-devel zlib-devel openssl-devel openssl
  else
    die "unsupported OS: need apt-get, dnf or yum to install the build dependencies"
  fi
}

# A truncated download is the usual way this step fails: the connection drops, wget leaves
# a short file behind, and a plain "does the file exist" check then treats it as complete.
# `gzip -t` reads the whole archive, so it catches that before tar does.
tarball_is_intact() {
  [[ -s "$1" ]] && gzip -t "$1" 2>/dev/null
}

fetch_source() {
  local file="${SOFT_ROOT}/${TARBALL}"
  mkdir -p "$SOFT_ROOT"
  if tarball_is_intact "$file"; then
    log "using ${file}"
    return 0
  fi
  rm -f "$file"
  # Up to three attempts. wget's own -t covers a dropped connection, but a server that closes
  # early makes wget exit 0 with a short file, and only the archive check notices that.
  # -T makes a stalled connection fail after 30s instead of hanging forever.
  local attempt
  for attempt in 1 2 3; do
    log "downloading ${DOWNLOAD_URL} (attempt ${attempt}/3)"
    if wget -q -T 30 -t 3 -O "$file" "$DOWNLOAD_URL" && tarball_is_intact "$file"; then
      return 0
    fi
    rm -f "$file"
  done
  die "could not download a valid ${TARBALL} from ${DOWNLOAD_URL}
       Fetch it some other way, put it in ${SOFT_ROOT}/, and run this again."
}

compile_nginx() {
  install_build_deps
  fetch_source

  rm -rf "$EXTRACT_DIR"
  (cd "$SOFT_ROOT" && tar -xzf "$TARBALL")
  [[ -x "${EXTRACT_DIR}/configure" ]] || die "unexpected archive layout: no ${EXTRACT_DIR}/configure"

  log "configuring nginx ${NGINX_VERSION} -> ${PREFIX}"
  # configure is not autoconf-generated and sources auto/options relative to the current
  # directory, so it has to be run as ./configure from inside the source tree.
  cd "$EXTRACT_DIR"
  ./configure \
    --prefix="$PREFIX" \
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

  log "compiling (make -j${MAKE_JOBS}); this takes a few minutes"
  make -j"$MAKE_JOBS"
  make install
  [[ -x "${PREFIX}/sbin/nginx" ]] || die "install failed: missing ${PREFIX}/sbin/nginx"
  log "installed $("${PREFIX}/sbin/nginx" -v 2>&1)"
}

link_nginx() {
  mkdir -p "$INSTALL_ROOT"
  # `ln -sfn` onto a real directory drops the link inside it instead of replacing it.
  if [[ -d "$NGINX_HOME" && ! -L "$NGINX_HOME" ]]; then
    die "${NGINX_HOME} is a real directory without a working nginx; move it aside first"
  fi
  ln -sfn "$PREFIX" "$NGINX_HOME"
  log "${NGINX_HOME} -> ${PREFIX}"
}

# Points the main config at conf/server/. Written only over a file that is ours or stock;
# a hand-written nginx.conf is reported, never edited.
ensure_layout() {
  mkdir -p "$SERVER_DIR" "$SSL_DIR" "$LOG_DIR"

  if [[ ! -f "$MAIN_CONF" ]] || is_stock_conf "$MAIN_CONF" || is_generated_conf "$MAIN_CONF"; then
    render_template "${TEMPLATE_DIR}/nginx.conf" "$MAIN_CONF"
    # Sites an older version of this tooling put in conf.d are no longer included and
    # would otherwise linger as dead files.
    local stale
    for stale in "${CONF_DIR}"/conf.d/jc-*.conf; do
      [[ -e "$stale" ]] && rm -f "$stale"
    done
    log "wrote ${MAIN_CONF} (includes ${SERVER_DIR}/*.conf)"
  elif grep -qE '^[[:space:]]*include[[:space:]]+[^;]*/server/\*\.conf' "$MAIN_CONF"; then
    log "${MAIN_CONF} is maintained by hand and already includes server/*.conf — left as is"
  else
    log "WARNING: ${MAIN_CONF} is maintained by hand and does not include server/*.conf."
    log "         Add this line inside its http { } block, or sites will not be loaded:"
    log "             include ${SERVER_DIR}/*.conf;"
  fi
}

main() {
  require_root

  if [[ -x "$NGINX_BIN" && "$FORCE" != true ]]; then
    log "nginx already installed: $("$NGINX_BIN" -v 2>&1) at ${NGINX_BIN} — not rebuilding"
    ensure_layout
    log "done. Next: apply-nginx-conf.sh"
    return 0
  fi

  if [[ -L "$NGINX_HOME" ]]; then
    local current
    current="$(cd "$NGINX_HOME" 2>/dev/null && pwd -P || true)"
    if [[ -n "$current" && "$current" != "$(mkdir -p "$PREFIX" && cd "$PREFIX" && pwd -P)" ]]; then
      die "${NGINX_HOME} points at ${current}, not ${PREFIX}.
       Switching versions would leave the sites and certificates behind in the old prefix.
       Copy conf/server and ssl across by hand, then remove the link and run this again."
    fi
  elif [[ -e "$NGINX_HOME" && ! -x "$NGINX_BIN" ]]; then
    die "${NGINX_HOME} exists but contains no nginx binary; move it aside first"
  fi

  compile_nginx
  link_nginx
  ensure_layout
  log "done. Next: apply-nginx-conf.sh"
}

main "$@"
