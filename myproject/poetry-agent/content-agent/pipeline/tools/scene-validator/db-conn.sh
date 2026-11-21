#!/usr/bin/env bash
# Shared read-only MySQL connection. Credentials come from the app config (never argv),
# overridable by DB_URL / DB_USER / DB_PASS. Only run SELECTs through this.
set -euo pipefail
CONFIG="${DB_CONFIG:-/Users/gqli/work/testserverV/vvv-link/src/main/resources/bootstrap-local.yml}"
DB_URL="${DB_URL:-$(awk '/url: jdbc:mysql/{print $2; exit}' "$CONFIG")}"
DB_USER="${DB_USER:-$(awk '/^    username:/{print $2; exit}' "$CONFIG")}"
MYSQL_PWD="${DB_PASS:-$(awk '/^    password:/{print $2; exit}' "$CONFIG")}"; export MYSQL_PWD
DB_HOST="${DB_HOST:-$(echo "$DB_URL" | sed -E 's#jdbc:mysql://([^:/]+).*#\1#')}"
DB_PORT="${DB_PORT:-$(echo "$DB_URL" | sed -E 's#jdbc:mysql://[^:]+:([0-9]+).*#\1#')}"
DB_NAME="${DB_NAME:-$(echo "$DB_URL" | sed -E 's#jdbc:mysql://[^/]+/([^?]+).*#\1#')}"
q() { mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -D "$DB_NAME" --default-character-set=utf8mb4 -N -B -e "$1"; }
qf() { mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -D "$DB_NAME" --default-character-set=utf8mb4 -t < "$1"; }
