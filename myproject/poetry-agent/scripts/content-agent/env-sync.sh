#!/usr/bin/env bash
# 把 content-agent/deploy/.env.example 里 .env 缺少的变量追加到 .env。
#
# - 只追加,已存在的行(包括被注释掉的以外的任何 NAME=...)绝不修改。
# - 令牌类变量(名称含 TOKEN/KEY/SECRET,且 .env.example 的值以 change-me 开头)用 openssl rand -hex 24 生成。
# - 示例值为空的密钥(例如 POETRY_LLM_API_KEY=)原样追加为空,需要你自己填。
# - 绝不输出任何值:只打印变量名和"已追加 / 已存在 / 已追加(空值,需手填)"。
# - 只从 .env 里提取变量名,从不读取或比较它的值。.env 权限保持 600。
set -euo pipefail
source "$(dirname "$0")/../lib.sh"

EXAMPLE="$CONTENT_DEPLOY/.env.example"
TARGET="$CONTENT_DEPLOY/.env"

if [[ ! -f "$EXAMPLE" ]]; then
  echo "错误: 找不到 $EXAMPLE(它由子任务 S5 维护),无法同步。" >&2
  exit 2
fi
command -v openssl >/dev/null 2>&1 || { echo "缺少命令: openssl" >&2; exit 1; }

umask 077
if [[ ! -f "$TARGET" ]]; then
  : >"$TARGET"
  echo ".env 不存在,已创建空文件(权限 600)"
fi
chmod 600 "$TARGET"

# 只取变量名。sed 只保留 NAME 部分,值不会进入任何变量。
existing="$(sed -nE 's/^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)=.*/\2/p' "$TARGET")"

# 文件末尾没有换行时先补一个,避免新行接在旧行后面。
# $(...) 会去掉末尾换行:最后一个字节不是换行时结果非空。
if [[ -s "$TARGET" && -n "$(tail -c 1 "$TARGET")" ]]; then
  printf '\n' >>"$TARGET"
fi

added=0
kept=0
needs_fill=""
name_re='^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$'

while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ "$line" =~ ^[[:space:]]*# || -z "${line//[[:space:]]/}" ]] && continue
  [[ "$line" =~ $name_re ]] || continue
  name="${BASH_REMATCH[1]}"
  example_value="${BASH_REMATCH[2]}"

  if printf '%s\n' "$existing" | grep -qxF "$name"; then
    echo "已存在   $name"
    kept=$((kept + 1))
    continue
  fi

  if [[ "$name" =~ (TOKEN|KEY|SECRET) && "$example_value" == change-me* ]]; then
    printf '%s=%s\n' "$name" "$(openssl rand -hex 24)" >>"$TARGET"
    echo "已追加   $name (随机生成)"
  elif [[ "$name" =~ (TOKEN|KEY|SECRET) && -z "$example_value" ]]; then
    printf '%s=\n' "$name" >>"$TARGET"
    echo "已追加   $name (空值,需手填)"
    needs_fill="$needs_fill $name"
  else
    printf '%s\n' "$line" >>"$TARGET"
    echo "已追加   $name"
  fi
  added=$((added + 1))
done <"$EXAMPLE"

chmod 600 "$TARGET"
echo "完成: 追加 $added 个, 已存在 $kept 个。"
[[ -n "$needs_fill" ]] && echo "仍需手填(值为空):$needs_fill"
exit 0
