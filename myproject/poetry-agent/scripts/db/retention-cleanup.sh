#!/usr/bin/env bash
# 学生端学习记录的保留期清理（未成年人数据合规项）。
#
# 为什么不是应用内定时器：应用不该拥有「删除未成年人数据」的能力。这个脚本由运维的 cron 调用，
# 连的是运维自己的凭据，应用进程即使被攻破也删不掉历史记录。
#
# 用法（在生产机上，由 root 的 crontab 或 systemd timer 调用）：
#   ./scripts/db/retention-cleanup.sh --dry-run     # 只数行，不删
#   ./scripts/db/retention-cleanup.sh               # 真删
#
# crontab 示例（每月 1 日 03:17，避开整点；日志留在 /var/log）：
#   17 3 1 * *  cd /opt/poetry && ./scripts/db/retention-cleanup.sh >> /var/log/poetry-retention.log 2>&1
#
# 前置：目标库已备份。SQL 文件里的保留期（事件 90 天 / 缺口 180 天 / 设备 180 天未活跃）是产品决定，
# 改保留期要改 SQL 文件本身，不要在这里加参数——两个地方定义同一个数字迟早会不一致。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SQL="${POETRY_RETENTION_SQL:-$HERE/../../testserverV/vvv-student/src/main/resources/db/student/retention_cleanup.sql}"
[[ -f "$SQL" ]] || SQL="/Users/gqli/work/testserverV/vvv-student/src/main/resources/db/student/retention_cleanup.sql"
[[ -f "$SQL" ]] || { echo "找不到 retention_cleanup.sql（用 POETRY_RETENTION_SQL 指定）" >&2; exit 1; }

# 连接信息只从环境变量或 ~/.my.cnf 取，绝不出现在命令行里（ps 能看到命令行）。
MYSQL_ARGS=(--defaults-file="${POETRY_MYSQL_CNF:-$HOME/.my.cnf}" --batch --skip-column-names)

DRY_RUN=0
case "${1:-}" in
  --dry-run) DRY_RUN=1 ;;
  "") ;;
  *) echo "用法: $0 [--dry-run]" >&2; exit 2 ;;
esac

count() { mysql "${MYSQL_ARGS[@]}" -e "SELECT COUNT(*) FROM $1 WHERE $2"; }

if [[ "$DRY_RUN" == 1 ]]; then
  echo "== 将要删除的行数（dry-run，不删任何东西） =="
  printf '%-24s %s\n' "student_event (>90d)"   "$(count student_event "created_at < UTC_TIMESTAMP() - INTERVAL 90 DAY")"
  printf '%-24s %s\n' "student_gap (>180d)"    "$(count student_gap   "created_at < UTC_TIMESTAMP() - INTERVAL 180 DAY")"
  printf '%-24s %s\n' "student_device (>180d)" "$(count student_device "last_seen_at < UTC_TIMESTAMP() - INTERVAL 180 DAY")"
  exit 0
fi

# 大表上单表 DELETE 带 LIMIT 更安全（MySQL 5.6 支持单表 DELETE ... LIMIT），但 retention_cleanup.sql
# 是权威版本，这里不复制它的逻辑。需要分片时按文件头的说明手工加 LIMIT 并重复执行。
echo "== $(date -u '+%Y-%m-%dT%H:%M:%SZ') 开始 =="
mysql "${MYSQL_ARGS[@]}" < "$SQL"
echo "== $(date -u '+%Y-%m-%dT%H:%M:%SZ') 完成 =="
