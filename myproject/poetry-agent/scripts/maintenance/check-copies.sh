#!/usr/bin/env bash
# 共享层的一致性检查（依据 docs/specs/2026-11-11-target-architecture.md §5）。
#
# 历史：曾经有「两份 scene-runtime + 两份契约」，靠本脚本比对。2026-11-11 之后 scene-runtime 只剩
# 一份（content-agent/pipeline 的那份已删，编译器直接指向 student-app/runtime），所以这里不再有
# 「两份内核」可比；剩下的是契约。
#
# 契约的归属已经定死：
#   content-agent/pipeline/contracts/   是**源头**（手写处，11 个文件）
#   student-app/runtime/contracts/      其中 3 个是**生成副本**（bundle.schema / vocabulary / sample）
#   student-app/production/contracts/   只被素材工具使用，不是副本
#   agent-authoring/contracts/          只被那 87 行脚本使用，不是副本
#
# 用法：
#   ./scripts/maintenance/check-copies.sh          检查，不一致退出 1，并打印修复命令
#   ./scripts/maintenance/check-copies.sh --write  从源头覆盖生成副本（只覆盖上表列的 3 个文件）
set -uo pipefail
source "$(dirname "$0")/../lib.sh"
status=0
WRITE=0
[[ "${1:-}" == "--write" ]] && WRITE=1

SHARED=(bundle.schema.json vocabulary.json sample.chun-wang.json)
SOURCE="$CONTENT_PIPELINE/contracts"
COPIES="$STUDENT_RUNTIME/contracts"

if [[ "$WRITE" == 1 ]]; then
  for f in "${SHARED[@]}"; do
    cp "$SOURCE/$f" "$COPIES/$f"
    printf 'wrote    contracts/%s\n' "$f"
  done
  echo "（已从 $SOURCE 覆盖生成副本；源头仍是唯一手写处）"
  exit 0
fi

echo "--- 契约（源头: content-agent/pipeline/contracts）"
for f in "${SHARED[@]}"; do
  if diff -q "$SOURCE/$f" "$COPIES/$f" >/dev/null 2>&1; then
    printf 'same     contracts/%s\n' "$f"
  else
    printf 'DIFFERS  contracts/%s  ← 运行 ./scripts/maintenance/check-copies.sh --write\n' "$f"
    diff -u "$SOURCE/$f" "$COPIES/$f" | sed -n '3,12p' | sed 's/^/           /'
    status=1
  fi
done

# 内核只允许一份。若有人重新复制出一份，这里必须失败——这正是本脚本存在的理由。
if [[ -d "$CONTENT_PIPELINE/scene-runtime" ]]; then
  printf 'DIFFERS  content-agent/pipeline/scene-runtime 又出现了（内核只允许一份）\n'
  status=1
else
  printf 'same     scene-runtime 只有一份（student-app/runtime/scene-runtime）\n'
fi

# 枚举：词表 vs schema / TypeScript / 编译规则 / Java（每一处的定义都要与词表逐项一致）
echo "--- vocabulary enumeration"
if node "$(dirname "$0")/check-vocabulary.mjs" "$PLATFORM_ROOT" "${VVV_POETRY:-$HOME/work/testserverV/vvv-poetry}"; then
  :
else
  status=1
fi

exit "$status"
