#!/usr/bin/env bash
# 构建 Studio 前端并把产物放到 nginx 直接服务的静态目录（104）。在克隆里以 **web 用户**运行，不要用 root。
#
#   ./scripts/deploy/publish-studio.sh                 # 装依赖 + 构建 + 同步到静态目录
#   ./scripts/deploy/publish-studio.sh --dry-run       # 只看会放什么进去，不动部署目录
#   ./scripts/deploy/publish-studio.sh --skip-install  # node_modules 已就绪时跳过 npm ci
#
# 为什么单独一个脚本，不在 publish.sh 里顺手带上：publish.sh 复制的是**提交里 git 跟踪的文件**，
# 而 dist 是 .gitignore 掉的构建产物——它进不了那条通道。前端因此走自己的路：
# 在克隆里构建，产物放进静态目录，nginx 的 root 指向那个静态目录。
#
# 静态目录默认 /home/web/webroot/poetry-studio（用 PAP_STUDIO_DIR 改）。它**不在** publish.sh
# 的部署目录里，所以 python 侧发布永远不碰它；反过来也一样。
#
# 前端只跟 agent-bff 说话，VITE_AGENT_BFF_URL=/ 让浏览器用同源相对路径（nginx 把
# /api/poetry/v1/agent/ 反代到 127.0.0.1:8100）。构建时把它烤进去，所以**换了 API 前缀要重新构建**。
set -euo pipefail

log() { printf '[studio] %s\n' "$*"; }
die() { printf '[studio] ERROR: %s\n' "$*" >&2; exit 1; }

# SRC 从脚本自己的位置找；把脚本放到克隆外面跑时（比如服务器上的 ~/bin，为了让克隆保持干净）
# 用 PAP_STUDIO_SRC 指到 content-agent/frontend。
SRC="${PAP_STUDIO_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../content-agent/frontend" && pwd -P)}"
TARGET="${PAP_STUDIO_DIR:-/home/web/webroot/poetry-studio}"
BFF_URL="${PAP_STUDIO_BFF_URL:-/}"

DRY_RUN=false
SKIP_INSTALL=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --skip-install) SKIP_INSTALL=true ;;
    -h | --help) sed -n '2,20p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

[[ "$(id -u)" -ne 0 ]] || die "以 web 用户运行，不要用 root：root 建出来的产物，nginx 与 web 都改不了"
for tool in npm tar; do
  command -v "$tool" >/dev/null 2>&1 || die "需要 $tool"
done
[[ -f "$SRC/package.json" ]] || die "找不到 $SRC/package.json"

if [[ "$SKIP_INSTALL" != true ]]; then
  log "npm ci（$SRC）"
  ( cd "$SRC" && npm ci --no-audit --no-fund )
fi

log "构建（VITE_AGENT_BFF_URL=$BFF_URL）"
( cd "$SRC" && VITE_AGENT_BFF_URL="$BFF_URL" npm run build )
[[ -f "$SRC/dist/index.html" ]] || die "构建完没有 dist/index.html"

if [[ "$DRY_RUN" == true ]]; then
  log "dist 内容（--dry-run，没有动 ${TARGET}）："
  ( cd "$SRC/dist" && find . -type f | sed 's/^/  /' | sort )
  exit 0
fi

mkdir -p "$TARGET" 2>/dev/null || die "建不了 ${TARGET}（web 用户对 /home/web/webroot 有写权限吗）"
[[ -w "$TARGET" ]] || die "${TARGET} 对 $(id -un) 不可写"
TARGET="$(cd "$TARGET" && pwd -P)"
case "$TARGET/" in
  "$SRC/"* | "$SRC"/) die "静态目录（${TARGET}）就是构建目录或在其内部" ;;
esac

# 先建到临时目录再换名：中途失败不会把一个正在服务的站点清空。
STAGE="$(mktemp -d "${TARGET}.staging.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
( cd "$SRC/dist" && tar cf - . ) | ( cd "$STAGE" && tar xf - )
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
# index.html 绝不能被缓存：它引用的 asset 文件名带 hash，缓存了旧 index 就等于旧站点。
[[ -f "$STAGE/index.html" ]] && chmod 644 "$STAGE/index.html"
OLD="${TARGET}.old.$$"
mv "$TARGET" "$OLD"
if mv "$STAGE" "$TARGET"; then
  trap - EXIT
  rm -rf "$OLD"
  log "已发布到 ${TARGET}"
else
  mv "$OLD" "$TARGET" 2>/dev/null || true
  die "换名失败，已还原 ${TARGET}"
fi
log "nginx 不需要 reload：静态文件换了内容，root 没变。"
