#!/usr/bin/env bash
# The tools a deploy needs besides the code: uv (Python) and Node (frontend). Both are
# installed into the invoking user's home, with no sudo and no change to shell profiles, so
# the web user can set up a bare machine by itself. Source this file; do not execute it.
#
#   jc_check_system_tools [lsof]   what only an administrator can install, reported all at once
#   jc_use_local_tools             put ~/.local/bin and a user-installed Node on PATH
#   jc_ensure_uv                   find uv, or install it into ~/.local/bin
#   jc_ensure_node                 find a usable Node, or install one under ~/.local
#
# Every function prints what it did and returns non-zero with instructions when it cannot
# proceed; none of them exits, so the caller decides how to stop.
#
# Env (all optional):
#   JC_NODE_MAJOR=20              Node line to install when none usable is found
#   JC_NODE_DIST_URLS="..."       space separated mirrors, tried in order
#   JC_UV_INSTALLER_URL=...       where to fetch uv's installer from
#   JC_FETCH_TIMEOUT=600          seconds allowed for one download
#   UV_DOWNLOAD_URL / UV_INSTALLER_GITHUB_BASE_URL   uv's own mirror switches, passed through
# shellcheck shell=bash

JC_NODE_MAJOR="${JC_NODE_MAJOR:-20}"
JC_NODE_DIST_URLS="${JC_NODE_DIST_URLS:-https://nodejs.org/dist https://npmmirror.com/mirrors/node}"
JC_UV_INSTALLER_URL="${JC_UV_INSTALLER_URL:-https://astral.sh/uv/install.sh}"
JC_FETCH_TIMEOUT="${JC_FETCH_TIMEOUT:-600}"

_jc_say() { printf '[env] %s\n' "$*"; }
_jc_err() { printf '[env] %s\n' "$*" >&2; }

_jc_local_bin() { printf '%s/.local/bin' "${HOME:?HOME is not set}"; }
_jc_node_link() { printf '%s/.local/node' "${HOME:?HOME is not set}"; }

_jc_path_has() {
  case ":${PATH}:" in *":$1:"*) return 0 ;; esac
  return 1
}

# Node versions Next.js 15 runs on: ^18.18 || ^19.8 || >=20. Taken from the installed
# next's own "engines" field, so a host that already has a working 18.x is left alone.
jc_node_version_ok() {
  local v="${1#v}" major rest minor
  [[ "$v" == *.* ]] || return 1
  major="${v%%.*}"
  rest="${v#*.}"
  minor="${rest%%.*}"
  [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] || return 1
  ((major >= 20)) && return 0
  ((major == 19)) && { ((minor >= 8)); return; }
  ((major == 18)) && { ((minor >= 18)); return; }
  return 1
}

jc_node_usable() {
  command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 || return 1
  jc_node_version_ok "$(node -v 2>/dev/null)"
}

# uv's dir goes after the system PATH (nothing there shadows a system tool). A user-installed
# Node goes in front, but only when the Node already on PATH is missing or too old: it exists
# because the system one was not good enough, and must not hide a good one.
jc_use_local_tools() {
  local bin node_bin
  bin="$(_jc_local_bin)"
  node_bin="$(_jc_node_link)/bin"
  if [[ -d "$bin" ]] && ! _jc_path_has "$bin"; then
    PATH="${PATH}:${bin}"
  fi
  if [[ -x "${node_bin}/node" ]] && ! _jc_path_has "$node_bin" && ! jc_node_usable; then
    PATH="${node_bin}:${PATH}"
  fi
  export PATH
}

jc_have_fetcher() {
  command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1
}

# -L: astral.sh answers with a 301 and nothing else. Without following it the "installer"
# is a 167 byte HTML page that sh then tries to run. wget follows redirects by default.
jc_fetch() {
  local url="$1" dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 15 --max-time "$JC_FETCH_TIMEOUT" -o "$dest" "$url" || { rm -f "$dest"; return 1; }
  elif command -v wget >/dev/null 2>&1; then
    wget -q -T 30 -t 2 -O "$dest" "$url" || { rm -f "$dest"; return 1; }
  else
    return 1
  fi
  [[ -s "$dest" ]]
}

jc_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  elif command -v openssl >/dev/null 2>&1; then
    openssl dgst -sha256 -r "$1" | cut -d' ' -f1
  else
    return 1
  fi
}

# Inside ~/.local so the finished directory is moved with a rename on the same filesystem.
_jc_mktmp() {
  mkdir -p "${HOME:?}/.local" && mktemp -d "${HOME}/.local/.jc-install.XXXXXX"
}

# Only ever removes a directory this file created.
_jc_cleanup_tmp() {
  case "${1:-}" in
    "${HOME:-/nonexistent}"/.local/.jc-install.*) [[ -d "$1" ]] && rm -rf "$1" ;;
  esac
  return 0
}

jc_platform_os() { uname -s; }
jc_platform_arch() { uname -m; }

_jc_glibc_version() {
  local out
  out="$(getconf GNU_LIBC_VERSION 2>/dev/null || true)"
  out="${out#glibc }"
  if [[ -z "$out" ]] && command -v ldd >/dev/null 2>&1; then
    out="$(ldd --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+$' || true)"
  fi
  printf '%s' "$out"
}

_jc_is_musl() {
  command -v ldd >/dev/null 2>&1 || return 1
  [[ "$(ldd --version 2>&1 || true)" == *[Mm]usl* ]]
}

# --- what an administrator has to provide ---------------------------------------------------

jc_check_system_tools() {
  local missing="" tool
  jc_have_fetcher || missing="${missing} curl"
  for tool in tar gzip "$@"; do
    command -v "$tool" >/dev/null 2>&1 || missing="${missing} ${tool}"
  done
  [[ -z "$missing" ]] && return 0
  _jc_err "ERROR: missing system tools:${missing}"
  _jc_err "       These cannot be installed without root. Ask an administrator to run:"
  _jc_err "           apt-get install -y${missing}      # Debian / Ubuntu"
  _jc_err "           yum install -y${missing}          # CentOS / RHEL"
  return 1
}

# --- uv -------------------------------------------------------------------------------------

_jc_uv_manual() {
  _jc_err "ERROR: uv is required and could not be installed automatically: $1"
  _jc_err "       Install it by hand as this user, then run this script again:"
  _jc_err "           curl -LsSf ${JC_UV_INSTALLER_URL} | sh"
  _jc_err "       or copy a uv binary to $(_jc_local_bin)/uv. On a host that cannot reach GitHub,"
  _jc_err "       set UV_INSTALLER_GITHUB_BASE_URL (or UV_DOWNLOAD_URL) to a mirror first."
}

jc_ensure_uv() {
  jc_use_local_tools
  command -v uv >/dev/null 2>&1 && return 0
  jc_have_fetcher || { _jc_uv_manual "neither curl nor wget is installed"; return 1; }

  local tmp
  tmp="$(_jc_mktmp)" || { _jc_uv_manual "cannot create a temporary directory under ${HOME}/.local"; return 1; }
  _jc_say "uv not found - installing it into $(_jc_local_bin) (no sudo, shell profiles untouched)"

  # The installer is saved and run as a file, not piped from curl into sh: a download that
  # stops halfway would otherwise execute the part that arrived.
  if ! jc_fetch "$JC_UV_INSTALLER_URL" "${tmp}/uv-install.sh"; then
    _jc_cleanup_tmp "$tmp"
    _jc_uv_manual "could not download ${JC_UV_INSTALLER_URL}"
    return 1
  fi
  # UV_INSTALL_DIR pins the binary to ~/.local/bin whatever XDG_BIN_HOME says; the installer
  # uses a flat layout for it, so the file lands exactly at ~/.local/bin/uv.
  if ! UV_INSTALL_DIR="$(_jc_local_bin)" UV_NO_MODIFY_PATH=1 sh "${tmp}/uv-install.sh"; then
    _jc_cleanup_tmp "$tmp"
    _jc_uv_manual "the installer script failed"
    return 1
  fi
  _jc_cleanup_tmp "$tmp"

  jc_use_local_tools
  command -v uv >/dev/null 2>&1 || { _jc_uv_manual "the installer finished but no uv appeared in $(_jc_local_bin)"; return 1; }
  _jc_say "uv $(uv --version 2>/dev/null | awk '{print $2}') installed"
}

# --- Node -----------------------------------------------------------------------------------

_jc_node_manual() {
  _jc_err "ERROR: Node ${JC_NODE_MAJOR} is required for the frontend and could not be installed automatically: $1"
  _jc_err "       Install Node (>= 18.18) by any route and make sure 'node' and 'npm' are on PATH, or unpack"
  _jc_err "       a Linux binary tarball from https://nodejs.org/dist/ so that ${HOME}/.local/node/bin/node exists."
  _jc_err "       To use another mirror: JC_NODE_DIST_URLS=\"https://host/path/node\" (it must contain"
  _jc_err "       latest-v${JC_NODE_MAJOR}.x/SHASUMS256.txt)."
}

jc_ensure_node() {
  jc_use_local_tools
  jc_node_usable && return 0

  if command -v node >/dev/null 2>&1; then
    _jc_say "node $(node -v 2>/dev/null) is on PATH but too old (Next.js needs >= 18.18) - installing Node ${JC_NODE_MAJOR} for this user"
  else
    _jc_say "node not found - installing Node ${JC_NODE_MAJOR} for this user (no sudo, shell profiles untouched)"
  fi

  local os arch platform link
  os="$(jc_platform_os)"
  arch="$(jc_platform_arch)"
  link="$(_jc_node_link)"
  [[ "$os" == Linux ]] || { _jc_node_manual "automatic install supports Linux only, this is ${os}"; return 1; }
  case "$arch" in
    x86_64 | amd64) platform=x64 ;;
    aarch64 | arm64) platform=arm64 ;;
    *) _jc_node_manual "no official Node ${JC_NODE_MAJOR} binary for ${arch}"; return 1 ;;
  esac

  # Official Linux binaries for Node 18+ need glibc 2.28; on an older or musl-based system
  # they fail with a "version GLIBC_x not found" error only when node first runs.
  if _jc_is_musl; then
    _jc_node_manual "this system uses musl libc (Alpine); the official binaries need glibc"
    return 1
  fi
  local glibc glibc_major glibc_minor
  glibc="$(_jc_glibc_version)"
  if [[ -n "$glibc" ]]; then
    glibc_major="${glibc%%.*}"
    glibc_minor="${glibc#*.}"
    glibc_minor="${glibc_minor%%.*}"
    if [[ "$glibc_major" =~ ^[0-9]+$ && "$glibc_minor" =~ ^[0-9]+$ ]] \
      && { ((glibc_major < 2)) || ((glibc_major == 2 && glibc_minor < 28)); }; then
      _jc_node_manual "glibc ${glibc} is older than 2.28, which the official Node ${JC_NODE_MAJOR} binaries need"
      return 1
    fi
  fi

  if [[ -e "$link" && ! -L "$link" ]]; then
    _jc_node_manual "${link} exists and is not a link this script created; refusing to replace it"
    return 1
  fi
  jc_have_fetcher || { _jc_node_manual "neither curl nor wget is installed"; return 1; }

  local tmp base sums line want_sha file ver actual name dest
  tmp="$(_jc_mktmp)" || { _jc_node_manual "cannot create a temporary directory under ${HOME}/.local"; return 1; }
  file=""
  for base in $JC_NODE_DIST_URLS; do
    sums="${tmp}/SHASUMS256.txt"
    if ! jc_fetch "${base}/latest-v${JC_NODE_MAJOR}.x/SHASUMS256.txt" "$sums"; then
      _jc_say "  ${base}: could not fetch the checksum list"
      continue
    fi
    line="$(grep -E "  node-v[0-9]+\.[0-9]+\.[0-9]+-linux-${platform}\.tar\.gz\$" "$sums" | head -1 || true)"
    if [[ -z "$line" ]]; then
      _jc_say "  ${base}: no linux-${platform} tarball listed"
      continue
    fi
    want_sha="${line%% *}"
    file="${line##* }"
    _jc_say "  downloading ${file} from ${base}"
    if ! jc_fetch "${base}/latest-v${JC_NODE_MAJOR}.x/${file}" "${tmp}/${file}"; then
      _jc_say "  ${base}: download failed"
      file=""
      continue
    fi
    actual="$(jc_sha256 "${tmp}/${file}" || true)"
    if [[ -z "$actual" || "$actual" != "$want_sha" ]]; then
      _jc_say "  ${base}: checksum does not match the listed value - discarding the file"
      rm -f "${tmp}/${file}"
      file=""
      continue
    fi
    break
  done
  if [[ -z "$file" ]]; then
    _jc_cleanup_tmp "$tmp"
    _jc_node_manual "no mirror in JC_NODE_DIST_URLS produced a verified tarball"
    return 1
  fi

  # node-v20.x.y-linux-x64.tar.gz -> node-v20.x.y-linux-x64, one version per directory with
  # ~/.local/node pointing at the current one, so a bad upgrade is undone by re-pointing it.
  name="${file%.tar.gz}"
  ver="${name#node-}"
  ver="${ver%%-linux*}"
  dest="${HOME}/.local/${name}"
  if ! tar -xzf "${tmp}/${file}" -C "$tmp"; then
    _jc_cleanup_tmp "$tmp"
    _jc_node_manual "the verified tarball could not be unpacked"
    return 1
  fi
  if [[ ! -x "${tmp}/${name}/bin/node" ]]; then
    _jc_cleanup_tmp "$tmp"
    _jc_node_manual "the tarball does not contain ${name}/bin/node"
    return 1
  fi
  if [[ -e "$dest" ]]; then
    if [[ ! -x "${dest}/bin/node" ]]; then
      _jc_cleanup_tmp "$tmp"
      _jc_node_manual "${dest} exists but holds no working node; remove it and run this again"
      return 1
    fi
  else
    mv "${tmp}/${name}" "$dest" || { _jc_cleanup_tmp "$tmp"; _jc_node_manual "could not move Node into ${dest}"; return 1; }
  fi
  _jc_cleanup_tmp "$tmp"
  ln -sfn "$name" "$link" || { _jc_node_manual "could not create the link ${link}"; return 1; }

  jc_use_local_tools
  if ! jc_node_usable; then
    _jc_node_manual "Node ${ver} was installed to ${dest} but does not run here (node -v: $("${link}/bin/node" -v 2>&1 | head -1))"
    return 1
  fi
  _jc_say "node $(node -v) and npm $(npm -v) installed in ${dest}"
}
