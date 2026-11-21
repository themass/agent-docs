#!/usr/bin/env bash
# 查看 dev-offline.sh 各服务的状态。只读,始终以 0 退出。
set -euo pipefail
source "$(dirname "$0")/_dev-offline-common.sh"

printf '%-8s %-6s %-8s %-10s %s\n' 服务 端口 pid 进程 健康
for name in $SERVICES_ALL; do
  port="$(port_of "$name")"
  pid="-"
  proc="未运行"
  health="-"
  if is_running "$name"; then
    pid="$(cat "$(pid_file "$name")")"
    proc="运行中"
    if is_ready "$name"; then health="就绪"; else health="未就绪($(http_code "$(health_url_of "$name")"))"; fi
  elif port_listening "$port"; then
    proc="外部占用"
  fi
  printf '%-8s %-6s %-8s %-10s %s\n' "$name" "$port" "$pid" "$proc" "$health"
done
echo "日志目录: $RUN_DIR/"
