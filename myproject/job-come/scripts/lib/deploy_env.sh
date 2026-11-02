#!/usr/bin/env bash
# Per-deployment settings that must be the same for every script and every user: the ports
# the services listen on, which nginx has to proxy to. Source this file; do not execute it.
#
#   <deploy dir>/.data/deploy.env        KEY=value lines, e.g.   JC_WEB_PORT=3001
#
# Why a file and not the shell environment: `JC_WEB_PORT=3001 ./scripts/frontend.sh start`
# works once, and the next `frontend.sh restart`, a cron job, or a `sudo` without -E starts
# on the default again - while nginx is still pointed at the first value. A file in the
# deployment directory is read the same way by all of them. `.data/` is never touched by
# publish.sh, so it survives a release.
#
# Precedence: a variable already set in the environment wins, so a one-off override on the
# command line still works. The file is parsed, never executed: only known keys are read,
# and the value is taken literally (no expansion, no command substitution).
# shellcheck shell=bash

_JC_DEPLOY_ENV_KEYS="JC_WEB_PORT JC_API_PORT JC_API_HOST JC_API_WORKERS JC_NGINX_SERVER_NAME JC_NGINX_HTTPS_PORT JC_START_TIMEOUT"

jc_load_deploy_env() {
  local root="$1" file line key value allowed
  file="${root}/.data/deploy.env"
  [[ -r "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    case "$line" in "" | "#"*) continue ;; esac
    [[ "$line" == *=* ]] || { printf '[deploy.env] ignoring a line without "=": %s\n' "$line" >&2; continue; }
    key="${line%%=*}"
    value="${line#*=}"
    key="${key//[[:space:]]/}"
    allowed=false
    for k in $_JC_DEPLOY_ENV_KEYS; do [[ "$k" == "$key" ]] && allowed=true; done
    if [[ "$allowed" != true ]]; then
      printf '[deploy.env] ignoring unknown key "%s" (allowed: %s)\n' "$key" "$_JC_DEPLOY_ENV_KEYS" >&2
      continue
    fi
    # Surrounding quotes are allowed and removed; nothing inside them is interpreted.
    if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then value="${value:1:${#value}-2}"; fi
    # An already-exported variable wins over the file.
    [[ -z "${!key+x}" ]] || continue
    printf -v "$key" '%s' "$value"
    export "$key"
  done <"$file"
}
