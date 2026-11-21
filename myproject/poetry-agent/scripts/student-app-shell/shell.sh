#!/usr/bin/env bash
# 移动壳(Capacitor)的入口脚本。不跑测试套件,不装 SDK/Xcode/CocoaPods,不改系统配置。
#   shell.sh check          静态检查(壳一致性 + tsc --noEmit + 语法)
#   shell.sh sync-android   make student-web → 写入运行时配置 → cap sync android
#   shell.sh sync-ios       同上,iOS(需要 Xcode + CocoaPods,本机没有时会失败并说明原因)
#   shell.sh env            探测 Android SDK / Java / Xcode / CocoaPods,只读
set -euo pipefail
source "$(dirname "$0")/../lib.sh"
SHELL_DIR="$STUDENT_APP/shell"

cmd="${1:-check}"

ensure_deps() {
  [[ -d "$SHELL_DIR/node_modules" ]] || (cd "$SHELL_DIR" && npm install --no-audit --no-fund)
}

# 只在本进程里给 Gradle 用:不写入 shell 配置文件。
android_env() {
  if [[ -z "${ANDROID_HOME:-}" && -d "$HOME/Library/Android/sdk" ]]; then
    export ANDROID_HOME="$HOME/Library/Android/sdk"
  fi
}

case "$cmd" in
  check)
    ensure_deps
    (cd "$SHELL_DIR" && node scripts/check-shell.mjs && npx tsc --noEmit -p tsconfig.json)
    node --check "$SHELL_DIR/src/native-adapter.js"
    node --check "$SHELL_DIR/scripts/prepare-web.mjs"
    bash -n "$0"
    echo "ok"
    ;;
  sync-android|sync-ios)
    ensure_deps
    platform="${cmd#sync-}"
    (cd "$PLATFORM_ROOT" && make student-web)
    (cd "$SHELL_DIR" && node scripts/prepare-web.mjs)
    if [[ ! -d "$SHELL_DIR/$platform" ]]; then
      echo "还没有 $platform 工程:先在 $SHELL_DIR 执行 npx cap add $platform" >&2
      exit 2
    fi
    (cd "$SHELL_DIR" && npx cap sync "$platform")
    ;;
  env)
    android_env
    echo "node  : $(node -v)"
    echo "java  : $(java -version 2>&1 | head -1)"
    echo "ANDROID_HOME=${ANDROID_HOME:-<未设置>}"
    if [[ -n "${ANDROID_HOME:-}" ]]; then
      echo "  platforms  : $(ls "$ANDROID_HOME/platforms" 2>/dev/null | tr '\n' ' ')"
      echo "  build-tools: $(ls "$ANDROID_HOME/build-tools" 2>/dev/null | tr '\n' ' ')"
    fi
    echo "xcode-select: $(xcode-select -p 2>&1)"
    command -v xcodebuild >/dev/null && xcodebuild -version 2>&1 | head -1 || true
    command -v pod >/dev/null && echo "pod: $(pod --version)" || echo "pod: 未安装"
    ;;
  *)
    echo "用法: $0 {check|sync-android|sync-ios|env}" >&2
    exit 64
    ;;
esac
