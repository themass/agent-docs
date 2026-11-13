#!/usr/bin/env bash
# 把 git 已提交的代码同步到部署目录。在克隆里以 web 用户运行，不要用 root。
#
#   ./scripts/publish.sh                      # 复制
#   ./scripts/publish.sh --dry-run            # 只看会新增、改动、删除什么
#   ./scripts/publish.sh --deploy             # 复制完在部署目录跑 deploy.sh
#   ./scripts/publish.sh --deploy --restart   # ...再重启 api 与 voice
#   ./scripts/publish.sh --deploy -- --skip-voice   # `--` 之后的参数传给 deploy.sh
#
# 部署目录默认 /home/web/webroot/companion-agent（用 CA_DEPLOY_DIR 改）。
#
# 复制的是**当前提交里 git 跟踪的文件**——所以没有 .git、没有 .venv、没有 pycache、没有
# 改了一半或未跟踪的文件，每次跑结果都一样。工作区必须干净，否则"提交里的"和"磁盘上的"
# 不是一回事；--allow-dirty 就照磁盘现状复制，并在 .deploy-version 里注明。
#
# 只删除**上一次发布放进去、这次提交已经没有**的文件（.deploy-manifest 记着清单）。
# 部署目录自己生成的东西永远不在清单里，永远不会被碰：.env、.venv、.data、logs。
#
# 发布不会影响正在运行的进程；新代码要 deploy.sh（依赖、迁移）加重启才生效。
set -euo pipefail

log() { printf '[publish] %s\n' "$*"; }
die() { printf '[publish] ERROR: %s\n' "$*" >&2; exit 1; }

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TARGET="${CA_DEPLOY_DIR:-/home/web/webroot/companion-agent}"

DRY_RUN=false
ALLOW_DIRTY=false
DO_DEPLOY=false
DO_RESTART=false
DEPLOY_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --allow-dirty) ALLOW_DIRTY=true ;;
    --deploy) DO_DEPLOY=true ;;
    --restart) DO_RESTART=true ;;
    -h | --help) sed -n '2,20p' "$0"; exit 0 ;;
    --) shift; DEPLOY_ARGS=("$@"); break ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

[[ "$(id -u)" -ne 0 ]] || die "以 web 用户运行，不要用 root：root 复制过去的文件，运行服务的用户改不了"
command -v git >/dev/null 2>&1 || die "需要 git"
command -v tar >/dev/null 2>&1 || die "需要 tar"
git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1 || die "${SRC} 不在 git 检出里；要从克隆里发布"

mkdir -p "$TARGET" 2>/dev/null || die "建不了 ${TARGET}（web 用户对 /home/web/webroot 有写权限吗）"
[[ -w "$TARGET" ]] || die "${TARGET} 对 $(id -un) 不可写"
TARGET="$(cd "$TARGET" && pwd -P)"
case "$TARGET/" in
  "$SRC/"* | "$SRC"/) die "部署目录（${TARGET}）就是源码目录或在其内部" ;;
esac
case "$SRC/" in
  "$TARGET/"*) die "源码目录（${SRC}）在部署目录（${TARGET}）内部" ;;
esac

if [[ "$ALLOW_DIRTY" != true ]]; then
  dirty="$(git -C "$SRC" status --porcelain --untracked-files=no -- . | head -5)"
  if [[ -n "$dirty" ]]; then
    printf '%s\n' "$dirty" >&2
    die "有未提交的改动（上面几行）。提交或 stash，或加 --allow-dirty"
  fi
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/publish.XXXXXX")"
trap '[[ -n "${WORK:-}" && -d "$WORK" ]] && rm -rf "$WORK"' EXIT

# 只取这个目录下被跟踪的文件。160000 是 gitlink（嵌套检出），tar 会把它当目录，
# 把里面碰巧存在的东西一起复制走，所以跳过。
git -C "$SRC" ls-files -s -z -- . | while IFS= read -r -d '' record; do
  mode="${record%% *}"
  path="${record#*$'\t'}"
  [[ "$mode" == 160000 ]] && continue
  [[ "$path" == *$'\n'* ]] && die "有被跟踪的路径含换行：拒绝处理"
  printf '%s\0' "$path"
done >"${WORK}/list.nul"
tr '\0' '\n' <"${WORK}/list.nul" | LC_ALL=C sort >"${WORK}/manifest.new"
[[ -s "${WORK}/manifest.new" ]] || die "git 在 ${SRC} 下列不出任何被跟踪的文件"

OLD_MANIFEST="${TARGET}/.deploy-manifest"
if [[ -f "$OLD_MANIFEST" ]]; then
  LC_ALL=C sort "$OLD_MANIFEST" >"${WORK}/manifest.old"
else
  : >"${WORK}/manifest.old"
fi
LC_ALL=C comm -13 "${WORK}/manifest.new" "${WORK}/manifest.old" >"${WORK}/removed"

added=0
changed=0
while IFS= read -r path; do
  if [[ ! -e "${TARGET}/${path}" && ! -L "${TARGET}/${path}" ]]; then
    added=$((added + 1))
  elif [[ -L "${SRC}/${path}" || -L "${TARGET}/${path}" ]]; then
    [[ "$(readlink "${SRC}/${path}" 2>/dev/null)" == "$(readlink "${TARGET}/${path}" 2>/dev/null)" ]] || changed=$((changed + 1))
  elif ! cmp -s "${SRC}/${path}" "${TARGET}/${path}"; then
    changed=$((changed + 1))
  fi
done <"${WORK}/manifest.new"
removed=$(wc -l <"${WORK}/removed" | tr -d ' ')

log "源码:    ${SRC}"
log "目标:    ${TARGET}"
log "提交:    $(git -C "$SRC" rev-parse --short HEAD) ($(git -C "$SRC" rev-parse --abbrev-ref HEAD))"
log "文件:    $(wc -l <"${WORK}/manifest.new" | tr -d ' ') 个被跟踪，新增 ${added}，改动 ${changed}，删除 ${removed}"
if [[ "$removed" -gt 0 ]]; then
  # 用 awk 而不是 `sed | head -20`：head 读够行数就关闭管道，sed 收到 SIGPIPE 退出 141，
  # 在 `set -o pipefail` + `set -e` 下会让整个脚本**静默中止**——删了一行都没删、一个文件都没复制。
  # 删除项少于 20 时不会触发，所以这个问题在小改动上一直看不出来。
  awk 'NR <= 20 { printf "           删除: %s\n", $0 }' "${WORK}/removed"
  [[ "$removed" -gt 20 ]] && log "           ... 另有 $((removed - 20)) 个"
fi

if [[ "$DRY_RUN" == true ]]; then
  log "dry run — 什么都没写"
  exit 0
fi

# 走 tar：保留可执行位，服务器上不需要 rsync，名单之外的东西一个也带不过去。
tar -C "$SRC" --null --no-recursion -cf - -T "${WORK}/list.nul" | tar -C "$TARGET" -xpf -

# 删提交里已经没有的。只删上次发布写过的路径，只删文件和符号链接，
# 绝不顺着路径跑到目标目录外面去。
while IFS= read -r path; do
  case "$path" in "" | /* | ../* | */../* | */.. | ..) continue ;; esac
  if [[ -f "${TARGET}/${path}" || -L "${TARGET}/${path}" ]]; then
    rm -f "${TARGET:?}/${path}"
    dir="$(dirname "$path")"
    while [[ "$dir" != "." && "$dir" != "/" ]]; do
      rmdir "${TARGET}/${dir}" 2>/dev/null || break
      dir="$(dirname "$dir")"
    done
  fi
done <"${WORK}/removed"

cp "${WORK}/manifest.new" "$OLD_MANIFEST"
{
  printf 'commit: %s\n' "$(git -C "$SRC" rev-parse HEAD)"
  printf 'branch: %s\n' "$(git -C "$SRC" rev-parse --abbrev-ref HEAD)"
  printf 'published: %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')"
  printf 'source: %s\n' "$SRC"
  [[ "$ALLOW_DIRTY" == true ]] && printf 'dirty: %s 个被跟踪文件与提交不一致\n' \
    "$(git -C "$SRC" status --porcelain --untracked-files=no -- . | wc -l | tr -d ' ')"
} >"${TARGET}/.deploy-version"
log "已发布到 ${TARGET}"

[[ -f "${TARGET}/server/.env" ]] || log "注意：${TARGET}/server/.env 还不存在——从 server/.env.example 复制一份再填值"

if [[ "$DO_DEPLOY" == true ]]; then
  log "在 ${TARGET} 里跑 deploy.sh"
  (cd "$TARGET" && ./scripts/deploy.sh ${DEPLOY_ARGS[@]+"${DEPLOY_ARGS[@]}"})
fi
if [[ "$DO_RESTART" == true ]]; then
  log "重启 ${TARGET} 里的服务"
  (cd "$TARGET" && ./scripts/process.sh restart)
fi

if [[ "$DO_DEPLOY" != true && "$DO_RESTART" != true ]]; then
  log "接下来，在 ${TARGET}：  ./scripts/deploy.sh  &&  ./scripts/process.sh restart"
fi
