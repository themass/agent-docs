#!/usr/bin/env bash
# 架构规则的机械检查（依据 docs/specs/2026-11-11-target-architecture.md §6）。
#
# 为什么是 shell + grep 而不是 lint 框架：这六条规则都是「某个目录里不得出现某种 import /
# 某个标识符」，用规则引擎反而要先学规则引擎。几十行 grep 就够，而且谁都能读、能改。
#
# 用法：
#   ./scripts/maintenance/check-architecture.sh          检查，违规即退出 1
#   ./scripts/maintenance/check-architecture.sh --list   只列规则名，不检查
#   ./scripts/maintenance/check-architecture.sh --baseline 打印当前违规（用于重构前记录基线）
set -uo pipefail
source "$(dirname "$0")/../lib.sh"

cd "$PLATFORM_ROOT"
RULES=("A1 源码不得 import 构建产物" "A2 视图不得 import 数据层" "A3 底层不得 import 上层" \
       "A4 内核不得有 I/O 与副作用" "A5 契约副本必须与源头一致" "A6 共享内核不得有两份")
fail=0
bad=()   # 每项 "<规则号> <文件>:<行> <内容>"

if [[ "${1:-}" == "--list" ]]; then printf '  %s\n' "${RULES[@]}"; exit 0; fi

note() { bad+=("$1"); }
# 排除构建产物、依赖、测试夹具与 vendored 上游：规则针对我们自己的源码。
SRC_DIRS=(student-app/frontend/src student-app/runtime/scene-runtime/src content-agent/pipeline)
EXCLUDES=(--exclude-dir=node_modules --exclude-dir=dist --exclude-dir=legacy --exclude-dir=upstream
          --exclude-dir=__pycache__ --exclude-dir=tests)

grep_files() { # 目录 正则 说明 → 输出 "文件:行:内容"
  local dir="$1" re="$2"
  grep -rnE "$re" "$dir" "${EXCLUDES[@]}" 2>/dev/null || true
}

# ---------- A1 源码不得 import 构建产物 ----------
# 现状里 src/*.js 直接 import ../dist/runtime/index.js，等于「改代码前必须先 build」。
# 目标是：内核由构建复制到 src/kernel/ 后再被 import，源码永不出现 dist/。
while IFS= read -r hit; do
  [[ -n "$hit" ]] && note "A1 $hit"
done < <(grep_files student-app/frontend/src "from ['\"][^'\"]*dist/")

# ---------- A2 视图不得 import 数据层 ----------
# views/* 直接 import data/* 会让「换数据源」变成改页面。视图只收 ViewModel。
while IFS= read -r hit; do
  [[ -n "$hit" ]] && note "A2 $hit"
done < <(grep_files student-app/frontend/src/views "from ['\"][^'\"]*(data|lesson)/")

# ---------- A3 底层不得 import 上层 ----------
# core/ 与内核只能往下，不许 import views/ui/data/lesson/character。
for bottom in student-app/frontend/src/core student-app/runtime/scene-runtime/src; do
  while IFS= read -r hit; do
    [[ -n "$hit" ]] && note "A3 $hit"
  done < <(grep_files "$bottom" "from ['\"][^'\"]*(views|ui|data|lesson|character)/")
done

# ---------- A4 内核不得有 I/O 与副作用 ----------
# 内核要能在浏览器/WebView/Node 三种环境下给出同样结果，所以不能有 I/O 与不确定性。
# 两个豁免不能省：
#   capabilities.ts 是「宿主注入」的类型声明，fetch 出现在接口签名里正是它的职责；
#   注释行在描述这条规则本身时不构成实现。
while IFS= read -r hit; do
  [[ -n "$hit" ]] && note "A4 $hit"
done < <(grep -rnE "(^|[^a-zA-Z_.])(fetch|XMLHttpRequest|localStorage|sessionStorage|document|window|navigator|Date\.now|Math\.random)\b" \
  student-app/runtime/scene-runtime/src "${EXCLUDES[@]}" 2>/dev/null \
  | grep -v '/capabilities\.ts:' | grep -vE ':[0-9]+: *([*]|//)' || true)

# ---------- A5 契约副本必须与源头一致 ----------
# 手写处只有一处；其余是生成物。这里只判定一致性，修复用 check-copies.sh。
if ! diff -q content-agent/pipeline/contracts/vocabulary.json \
             student-app/runtime/contracts/vocabulary.json >/dev/null 2>&1; then
  note "A5 vocabulary.json 两份不一致（源头 contracts/vocabulary.json）"
fi
if ! diff -q content-agent/pipeline/contracts/bundle.schema.json \
             student-app/runtime/contracts/bundle.schema.json >/dev/null 2>&1; then
  note "A5 bundle.schema.json 两份不一致（源头 contracts/bundle.schema.json）"
fi

# ---------- A6 共享内核不得有两份 ----------
if [[ -d content-agent/pipeline/scene-runtime && -d student-app/runtime/scene-runtime ]]; then
  if ! diff -rq content-agent/pipeline/scene-runtime/src student-app/runtime/scene-runtime/src >/dev/null 2>&1; then
    note "A6 两份 scene-runtime/src 内容不同（应改为单向生成）"
  else
    note "A6 两份 scene-runtime 内容相同但仍各存一份（技术债：应改为单向生成）"
  fi
fi

# ---------- 输出 ----------
if [[ "${1:-}" == "--baseline" ]]; then
  echo "当前违规（基线）："
  printf '%s\n' "${bad[@]}" | sed 's/^/  /'
  echo "共 ${#bad[@]} 条。"
  exit 0
fi

printf '%-4s %s\n' "规则" "说明"
for r in "${RULES[@]}"; do
  n="${r%% *}"
  count=$(printf '%s\n' "${bad[@]:-}" | grep -c "^$n " || true)
  if [[ "$count" -eq 0 ]]; then printf '%-4s ok   %s\n' "$n" "${r#* }"
  else printf '%-4s FAIL %s（%s 处）\n' "$n" "${r#* }" "$count"; fail=1; fi
done
if [[ "$fail" -ne 0 ]]; then
  echo
  printf '%s\n' "${bad[@]}" | sed 's/^/  /' | head -40
fi
exit "$fail"
