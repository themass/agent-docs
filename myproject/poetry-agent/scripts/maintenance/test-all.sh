#!/usr/bin/env bash
# 统一测试入口：开发期间不跑，留到最后一次性运行。
# 不连数据库、不启动容器、不访问私服；Java 部分用离线 Maven + 内存库（H2）。
# 用法：./scripts/maintenance/test-all.sh [--skip-java] [--list]
#   --skip-java  跳过 Java 部分
#   --list       只打印将要执行的步骤名，不执行任何命令（用来核对接线，不会跑测试）
# 任何一步失败，整体退出码非 0；最后打印汇总表。
set -uo pipefail
source "$(dirname "$0")/../lib.sh"

SKIP_JAVA=0; LIST_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --skip-java) SKIP_JAVA=1 ;;
    --list) LIST_ONLY=1 ;;
  esac
done
TESTSERVER="${TESTSERVER_ROOT:-/Users/gqli/work/testserverV}"
LOG_DIR=""
[ "$LIST_ONLY" = 1 ] || LOG_DIR="$(mktemp -d /tmp/poetry-test-all.XXXXXX)"
names=(); results=()

step() { # name, command...
  local name="$1"; shift
  if [ "$LIST_ONLY" = 1 ]; then printf '  %s\n' "$name"; return 0; fi
  local log="$LOG_DIR/$(echo "$name" | tr ' /' '__').log"
  printf '>> %s\n' "$name"
  if "$@" >"$log" 2>&1; then names+=("$name"); results+=("PASS")
  else names+=("$name"); results+=("FAIL  (log: $log)"); fi
}

cd "$PLATFORM_ROOT"

# --- 静态检查 ---
step "bash -n  所有脚本"           bash -c 'for f in $(find scripts content-agent/pipeline/tools -name "*.sh"); do bash -n "$f" || exit 1; done'
step "ruff     content-agent/agent" uv run --offline ruff check content-agent/agent
step "uv lock  一致性"             uv lock --check --offline
# 分层与依赖方向的机械检查（docs/specs/2026-11-11-target-architecture.md §6）。
# 放在副本检查之前：它能抓出「源码 import 构建产物」「视图 import 数据层」这类结构问题，
# 这些问题比副本漂移更根本。
step "架构规则(分层/依赖/契约/内核唯一)" ./scripts/maintenance/check-architecture.sh
step "两份副本一致"                ./scripts/maintenance/check-copies.sh
step "目录布局合规"                ./scripts/maintenance/check-layout.sh
step "夹具包可编译(素材表与登记簿未漂移)" python3 ./scripts/maintenance/build_fixture_bundle.py --check
step "profile  Soul/Skill/MCP 策略" ./scripts/content-agent/profile-check.sh

# --- Python（pytest：根配置的 testpaths = content-agent/agent + student-app/agent/tests）---
# 根项目自身 dependencies 是空的，workspace 成员的依赖只有 --all-packages 才会装。
# 不带它时 student-app/agent 与 content-agent/agent/* 的 import 全部失败（首次跑 test-all 时踩过）。
step "uv       workspace 成员依赖就绪" uv sync --all-packages --offline
step "pytest   agent 与学生端 agent" uv run --offline pytest
# dev-mock 不在根 testpaths 里；它自己的 conftest 负责 sys.path，所以单独一步，失败时好归因
step "pytest   dev-mock(本地 mock 域 API)" uv run --offline pytest content-agent/deploy/dev-mock/tests

# --- Node（运行时内核、学生端、素材工具、Studio）---
step "student-app  scene-runtime + frontend" ./scripts/student-app/verify.sh
step "student-app  前端单测(node --test)" bash -c 'cd student-app/frontend && node --test tests/'
step "production   素材机检/登记簿/播放器(node --test)" bash -c 'cd student-app/production && node --test tools/tests/'
# 内核只剩一份（student-app/runtime/scene-runtime），它由上一行的 verify.sh 覆盖。
# 原来的 "content-agent scene-runtime" 步骤随重复副本一起删除，避免检查一个不存在的目录。
# Studio 需要先 npm install。这里不联网安装（测试步骤里不应悄悄改环境），缺依赖就给出明确提示
STUDIO_NEEDS='[ -d node_modules ] || { echo "缺 node_modules:先在 content-agent/frontend 执行 npm install"; exit 3; }'
step "studio     Poetry Studio 类型检查(tsc)" bash -c "cd content-agent/frontend && $STUDIO_NEEDS; npm run -s typecheck"
step "studio     Poetry Studio 单测(vitest)" bash -c "cd content-agent/frontend && $STUDIO_NEEDS; npm test --silent"

# --- 校验器：只确认它能运行并给出结论。BLOCKED 是内容/核查状态，不是测试失败 ---
step "校验器能运行并给出 verdict"  bash -c 'cd content-agent/pipeline && node tools/scene-validator/validate.mjs contracts/sample.chun-wang.json --facts contracts/facts.chun-wang.json 2>&1 | grep -E "\"verdict\": \"(COMPILES|BLOCKED)\""'

# --- Java（离线 Maven，内存库）---
if [ "$SKIP_JAVA" = 0 ]; then
  step "java     vvv-poetry + vvv-roles + vvv-student" bash -c "cd '$TESTSERVER' && mvn -o -q -pl vvv-poetry,vvv-roles,vvv-student test"
fi

if [ "$LIST_ONLY" = 1 ]; then
  echo "(--list: 以上是将要执行的步骤，没有运行任何命令)"
  exit 0
fi

echo
printf '%-44s %s\n' "步骤" "结果"
printf '%-44s %s\n' "--------------------------------------------" "------"
fail=0
for i in "${!names[@]}"; do
  printf '%-44s %s\n' "${names[$i]}" "${results[$i]}"
  [[ "${results[$i]}" == FAIL* ]] && fail=1
done
echo
echo "日志目录: $LOG_DIR"
echo "未包含: 真实数据库、Docker 镜像构建、容器启动、浏览器/真机、数据库迁移脚本。"
exit "$fail"
