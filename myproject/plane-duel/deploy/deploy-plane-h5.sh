#!/bin/bash
# plane-duel H5 发布：拉代码 -> 测试 -> 构建 -> 同步到 nginx 站点目录
#
# 权威版本就是这份（agent-docs myproject/plane-duel/deploy/）。
# 服务器上的执行副本：8.217.122.83:/root/work/deploy-plane-h5.sh
# （改完这里就 scp 过去，两边别各自演化。）
#
# 前提（仅应用服务器本机执行）：
#   - /root/work/agent-docs 是本仓库的 clone（git 凭据已配好）
#   - node20 + pnpm 在 /usr/local/node20/bin
#   - nginx 站点根 /home/web/webroot/plane-duel（game.ok123find.top server 块 root）
#
# 用法: /root/work/deploy-plane-h5.sh [--skip-test]
#   --skip-test  跳过 pnpm -r test，只构建发布（应急用）
set -euo pipefail
export PATH=/usr/local/node20/bin:$PATH
REPO=/root/work/agent-docs
APP=$REPO/myproject/plane-duel/apps/client
DST=/home/web/webroot/plane-duel/
cd "$REPO"
git pull --ff-only
if [ "${1:-}" != "--skip-test" ]; then pnpm -C "$APP/../.." -r test; fi
pnpm -C "$APP" build:h5
rsync -a --delete "$APP/dist/" "$DST"
chown -R web:web "$DST"
# 自检：本机回环 + 域名解析（证书是 game 域名的 LE 证书，严格校验即可）
echo "deployed: $(curl -s -o /dev/null -w "%{http_code}" --resolve game.ok123find.top:443:127.0.0.1 https://game.ok123find.top/)"
