#!/usr/bin/env bash
# 停止 dev-offline.sh 启动的所有进程(按启动的相反顺序,递归结束进程树)。保留日志。
# 只按 .run/*.pid 里记录的 pid 动手,不按进程名或端口杀进程。
set -euo pipefail
source "$(dirname "$0")/_dev-offline-common.sh"

echo "== 停止本地离线演示 =="
for name in studio bff worker mcp mock; do
  stop_service "$name"
done

for name in $SERVICES_ALL; do
  port="$(port_of "$name")"
  if port_listening "$port"; then
    echo "提示: 端口 $port 仍有进程在监听(不是本脚本记录的 pid,未处理)。"
  fi
done
echo "日志保留在 $RUN_DIR/"
