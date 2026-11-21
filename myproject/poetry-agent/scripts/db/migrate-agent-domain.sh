#!/usr/bin/env bash
# Apply the agent-domain DDL to the configured Poetry schema.
# This script never uses mysql --force. It snapshots the current Poetry schema definition first.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEFAULT_DB_HELPER="/Users/gqli/work/xuexi/poetry-agent-platform/content-agent/pipeline/tools/scene-validator/db-conn.sh"
MIGRATION="${POETRY_AGENT_MIGRATION:-/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V007__agent_domain_audit.sql}"
RECOVERY_MIGRATION="${POETRY_AGENT_RECOVERY_MIGRATION:-/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/recovery/V007__agent_domain_audit_mysql56_resume.sql}"
AUDIT="${POETRY_AUDIT_SQL:-/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/audit_integrity_checks.sql}"
DB_HELPER="${POETRY_DB_HELPER:-$DEFAULT_DB_HELPER}"
BACKUP_ROOT="${POETRY_DB_BACKUP_ROOT:-$ROOT/.local-db-backups}"

[[ -r "$DB_HELPER" ]] || { echo "database helper is not readable: $DB_HELPER" >&2; exit 2; }
[[ -r "$MIGRATION" ]] || { echo "migration is not readable: $MIGRATION" >&2; exit 2; }
[[ -r "$RECOVERY_MIGRATION" ]] || { echo "recovery migration is not readable: $RECOVERY_MIGRATION" >&2; exit 2; }
[[ -r "$AUDIT" ]] || { echo "audit SQL is not readable: $AUDIT" >&2; exit 2; }

# The helper reads credentials from the existing local service configuration. It deliberately
# never writes credentials to stdout or to this backup directory.
# shellcheck source=/dev/null
source "$DB_HELPER"

stamp="$(date +%Y%m%dT%H%M%S%z)"
backup_dir="$BACKUP_ROOT/$stamp-agent-domain-v007"
mkdir -p "$backup_dir"

schema="$(q 'SELECT DATABASE()')"
server_version="$(q 'SELECT VERSION()')"
printf '%s\n' "$schema" > "$backup_dir/database.txt"
printf '%s\n' "$server_version" > "$backup_dir/server-version.txt"
shasum -a 256 "$MIGRATION" "$RECOVERY_MIGRATION" > "$backup_dir/migration.sha256"

# V007 is not replay-safe because MySQL 5.6 DDL autocommits. A known first attempt on
# November 6, 2026 can leave exactly the first five tables committed; handle only that narrow
# recovery shape, and refuse every other partial or duplicate state.
agent_table_count="$(q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN ('poetry_agent_task','poetry_agent_run','poetry_agent_mandate','poetry_agent_proposal','poetry_agent_review','poetry_agent_tool_receipt','poetry_agent_event','poetry_agent_profile_version','poetry_agent_compile_request')")"
version7_count="$(q 'SELECT COUNT(*) FROM poetry_schema_version WHERE version_no=7')"
apply_sql="$MIGRATION"
if [[ "$agent_table_count" == "0" && "$version7_count" == "0" ]]; then
  apply_mode="clean-v007"
elif [[ ( "$agent_table_count" == "5" || "$agent_table_count" == "9" ) && "$version7_count" == "0" ]]; then
  apply_mode="mysql56-v007-resume"
  apply_sql="$RECOVERY_MIGRATION"
else
  echo "Refusing agent migration: existing agent tables=$agent_table_count, schema version 7 rows=$version7_count" >&2
  exit 3
fi

q 'SELECT version_no, description FROM poetry_schema_version ORDER BY version_no' > "$backup_dir/poetry_schema_version.before.tsv"
q "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name LIKE 'poetry\\_%' ORDER BY table_name" > "$backup_dir/poetry_tables.before.txt"
: > "$backup_dir/poetry_schema.before.sql"
while IFS= read -r table; do
  printf '\n-- %s\n' "$table" >> "$backup_dir/poetry_schema.before.sql"
  q "SHOW CREATE TABLE \`$table\`" >> "$backup_dir/poetry_schema.before.sql"
done < "$backup_dir/poetry_tables.before.txt"

# Explicitly verify the known V006 historical state before applying the V007 ledger repair.
for table in poetry_asset poetry_script poetry_script_asset; do
  found="$(q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='$table'")"
  [[ "$found" == "1" ]] || { echo "Refusing V007: expected V006 table missing: $table" >&2; exit 4; }
done

printf '%s\n' "$apply_mode" > "$backup_dir/apply-mode.txt"
qf "$apply_sql"

q 'SELECT version_no, description FROM poetry_schema_version ORDER BY version_no' > "$backup_dir/poetry_schema_version.after.tsv"
q "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name LIKE 'poetry\\_%' ORDER BY table_name" > "$backup_dir/poetry_tables.after.txt"
post_agent_table_count="$(q "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN ('poetry_agent_task','poetry_agent_run','poetry_agent_mandate','poetry_agent_proposal','poetry_agent_review','poetry_agent_tool_receipt','poetry_agent_event','poetry_agent_profile_version','poetry_agent_compile_request')")"
[[ "$post_agent_table_count" == "9" ]] || { echo "V007 incomplete: expected 9 agent tables, got $post_agent_table_count" >&2; exit 5; }
[[ "$(q 'SELECT COUNT(*) FROM poetry_schema_version WHERE version_no=6')" == "1" ]] || { echo 'V006 ledger repair failed' >&2; exit 5; }
[[ "$(q 'SELECT COUNT(*) FROM poetry_schema_version WHERE version_no=7')" == "1" ]] || { echo 'V007 ledger row missing' >&2; exit 5; }

# This is post-migration integrity verification, not a business acceptance test.
mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -D "$DB_NAME" --default-character-set=utf8mb4 -N -B < "$AUDIT" > "$backup_dir/audit-c1-c9.tsv"
awk -F '\t' '$2 != 0 { print }' "$backup_dir/audit-c1-c9.tsv" > "$backup_dir/audit-nonzero.tsv"
if [[ -s "$backup_dir/audit-nonzero.tsv" ]]; then
  echo "V007 applied but integrity audit contains non-zero rows; see $backup_dir/audit-nonzero.tsv" >&2
  exit 6
fi

printf 'Applied agent-domain schema (%s) to %s (MySQL %s). Backup and audit: %s\n' "$apply_mode" "$schema" "$server_version" "$backup_dir"
