#!/usr/bin/env bash
# Run a .sql file containing SELECTs only, against the real base, and print a table.
#   usage: ./db-readonly.sh gap-report.sql
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/db-conn.sh"
sql="$(cat "$1")"
if echo "$sql" | grep -qiE '\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT)\b'; then
  echo "refusing: $1 contains a non-SELECT statement" >&2; exit 2
fi
qf "$1"
