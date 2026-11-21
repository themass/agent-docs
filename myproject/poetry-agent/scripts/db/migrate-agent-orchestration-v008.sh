#!/usr/bin/env bash
# Apply ONLY V008 after the V007 agent-domain migration. Never uses mysql --force.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB_HELPER="${POETRY_DB_HELPER:-/Users/gqli/work/xuexi/poetry-agent-platform/content-agent/pipeline/tools/scene-validator/db-conn.sh}"
MIGRATION="${POETRY_AGENT_ORCHESTRATION_MIGRATION:-/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V008__agent_orchestration_state.sql}"
BACKUP_ROOT="${POETRY_DB_BACKUP_ROOT:-$ROOT/.local-db-backups}"
[[ -r "$DB_HELPER" ]] || { echo "database helper is not readable: $DB_HELPER" >&2; exit 2; }
[[ -r "$MIGRATION" ]] || { echo "migration is not readable: $MIGRATION" >&2; exit 2; }
# shellcheck source=/dev/null
source "$DB_HELPER"
stamp="$(date +%Y%m%dT%H%M%S%z)"
backup_dir="$BACKUP_ROOT/$stamp-agent-orchestration-v008"
mkdir -p "$backup_dir"
q 'SELECT DATABASE()' > "$backup_dir/database.txt"
q 'SELECT VERSION()' > "$backup_dir/server-version.txt"
q 'SELECT version_no,description FROM poetry_schema_version ORDER BY version_no' > "$backup_dir/schema-version.before.tsv"
q 'SHOW CREATE TABLE poetry_agent_task' > "$backup_dir/poetry_agent_task.before.sql"
q 'SHOW CREATE TABLE poetry_agent_run' > "$backup_dir/poetry_agent_run.before.sql"
shasum -a 256 "$MIGRATION" > "$backup_dir/migration.sha256"
[[ "$(q 'SELECT COUNT(*) FROM poetry_schema_version WHERE version_no=7')" == "1" ]] || { echo 'V007 is required before V008' >&2; exit 3; }
[[ "$(q 'SELECT COUNT(*) FROM poetry_schema_version WHERE version_no=8')" == "0" ]] || { echo 'V008 is already recorded; refusing replay because MySQL 5.6 DDL autocommits' >&2; exit 4; }
qf "$MIGRATION"
[[ "$(q 'SELECT COUNT(*) FROM poetry_schema_version WHERE version_no=8')" == "1" ]] || { echo 'V008 ledger write missing' >&2; exit 5; }
for column in title instructions requested_profile requested_role active_run_id; do
  [[ "$(q "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='poetry_agent_task' AND column_name='$column'")" == "1" ]] || { echo "missing poetry_agent_task.$column" >&2; exit 5; }
done
for column in mandate_id profile_name runtime_thread_id runtime_run_id reason; do
  [[ "$(q "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='poetry_agent_run' AND column_name='$column'")" == "1" ]] || { echo "missing poetry_agent_run.$column" >&2; exit 5; }
done
q 'SELECT version_no,description FROM poetry_schema_version ORDER BY version_no' > "$backup_dir/schema-version.after.tsv"
echo "V008 applied; backup: $backup_dir"
