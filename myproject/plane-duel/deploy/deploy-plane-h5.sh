#!/bin/bash
# plane-duel H5 发布：从 GitHub 同步到本地 work 目录 -> 在 work 目录里测试+编译 -> 发布到 nginx 站点根
#
# 只管前端 H5。后端（testserverV / vvv-link jar）有独立部署流程，不在本脚本内。
#
# 权威版本：agent-docs myproject/plane-duel/deploy/deploy-plane-h5.sh
# 服务器执行副本：8.217.122.83:/root/work/deploy-plane-h5.sh
# （改完这份就 scp 过去覆盖，两边不各自演化。）
#
# 流程：
#   1) 同步：work 目录不存在 -> 从 GitHub clone；已存在 -> git pull --ff-only。
#      work 目录是发布副本，代码只在 GitHub 上改；一旦本地有提交/改动偏离远端，
#      pull 直接报错停下（不覆盖任何本地内容），人工确认后 rm -rf 重新 clone。
#   2) 编译：在 work 目录内的 apps/client 里 pnpm install / test / build:h5
#   3) 发布：rsync dist -> nginx 站点根，chown web，curl 严格校验自检
#
# 前提（仅应用服务器本机执行）：
#   - git 能读该仓库（HTTPS 凭据或 SSH key 已配好）
#   - node20 + pnpm 在 /usr/local/node20/bin
#   - nginx 站点根 /home/web/webroot/plane-duel（game.ok123find.top server 块 root）
#
# 用法: /root/work/deploy-plane-h5.sh [--skip-test]
#   --skip-test  跳过 pnpm -r test，只构建发布（应急用）
set -euo pipefail
export PATH=/usr/local/node20/bin:$PATH

GIT_URL="${GIT_URL:-https://github.com/themass/agent-docs.git}"
BRANCH="${BRANCH:-main}"
WORK=/root/work
REPO=$WORK/agent-docs
SUB=myproject/plane-duel
APP=$REPO/$SUB/apps/client
DST=/home/web/webroot/plane-duel/

# ---------------------------------------------------------- 1) 从 GitHub 同步
if [ -d "$REPO/.git" ]; then
  echo "== sync $GIT_URL ($BRANCH) -> $REPO"
  git -C "$REPO" pull --ff-only origin "$BRANCH"
  git -C "$REPO" log --oneline -1
else
  echo "== clone $GIT_URL -> $REPO"
  mkdir -p "$WORK"
  git clone --branch "$BRANCH" "$GIT_URL" "$REPO"
fi

# --------------------------------------------------------- 2) work 目录内编译
pnpm -C "$APP/../.." install --frozen-lockfile
if [ "${1:-}" != "--skip-test" ]; then pnpm -C "$APP/../.." -r test; fi
pnpm -C "$APP" build:h5

# ---------------------------------------------------------- 3) 发布 + 自检
rsync -a --delete "$APP/dist/" "$DST"
chown -R web:web "$DST"
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  --resolve game.ok123find.top:443:127.0.0.1 https://game.ok123find.top/)
echo "deployed: $CODE  (site=$(git -C "$REPO" rev-parse --short HEAD))"
[ "$CODE" = "200" ] || exit 1
