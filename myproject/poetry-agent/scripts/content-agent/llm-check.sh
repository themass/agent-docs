#!/usr/bin/env bash
# 检查大模型网关是否可用:只请求模型列表接口,不发提示词,不产生推理费用。
#
# 输出(仅此):HTTP 状态码、网关返回的模型 id 里是否包含 PRIMARY / FALLBACK 两个模型名(布尔)、耗时。
# 绝不回显:密钥、主机名、完整 URL、查询串、响应正文。密钥通过 curl -K 的标准输入传递,不出现在进程参数里。
#
# 退出码: 0 状态码 200 且两个模型都在; 1 请求失败或模型缺失; 2 配置缺失。
set -uo pipefail
source "$(dirname "$0")/../lib.sh"

ENV_FILE="$CONTENT_DEPLOY/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "错误: $ENV_FILE 不存在。先运行 make content-env-sync。" >&2
  exit 2
fi
command -v curl >/dev/null 2>&1 || { echo "缺少命令: curl" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "缺少命令: python3" >&2; exit 2; }

# 子 shell 里 source,变量不会泄漏到调用者环境。
(
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  missing=""
  for v in POETRY_LLM_API_BASE POETRY_LLM_API_KEY POETRY_LLM_MODEL_PRIMARY POETRY_LLM_MODEL_FALLBACK; do
    [[ -n "${!v:-}" ]] || missing="$missing $v"
  done
  if [[ -n "$missing" ]]; then
    echo "错误: 以下变量为空或未设置:$missing" >&2
    exit 2
  fi

  base="${POETRY_LLM_API_BASE%/}"
  case "$base" in
    http://*) scheme="http (明文)" ;;
    https://*) scheme="https" ;;
    *) echo "错误: POETRY_LLM_API_BASE 不是 http(s) 地址。" >&2; exit 2 ;;
  esac

  body="$(mktemp "${TMPDIR:-/tmp}/llm-check.XXXXXX")"
  trap 'rm -f "$body"' EXIT

  fetch() { # $1=完整 URL。URL 与密钥都走 -K 标准输入,不进 argv;stderr 丢弃以免泄漏主机名。
    printf 'url = "%s"\nheader = "Authorization: Bearer %s"\n' "$1" "$POETRY_LLM_API_KEY" |
      curl -s -m 20 -K - -o "$body" -w '%{http_code}' 2>/dev/null
  }

  start="$(python3 -c 'import time; print(time.time())')"
  code="$(fetch "$base/models")"
  [[ "$code" == "404" ]] && code="$(fetch "$base/v1/models")"
  code="${code:-000}"
  elapsed="$(python3 -c "import time; print(round((time.time() - $start) * 1000))")"

  # 只做布尔判断;模型 id 从响应里取,但不打印。
  verdict="$(
    LLM_BODY="$body" python3 - <<'PY'
import json, os
try:
    data = json.load(open(os.environ["LLM_BODY"], encoding="utf-8"))
    ids = {m.get("id") for m in data.get("data", []) if isinstance(m, dict)}
except Exception:
    ids = set()
print(int(os.environ["POETRY_LLM_MODEL_PRIMARY"] in ids), int(os.environ["POETRY_LLM_MODEL_FALLBACK"] in ids))
PY
  )"
  primary="${verdict%% *}"
  fallback="${verdict##* }"
  yn() { [[ "$1" == "1" ]] && echo 是 || echo 否; }

  echo "协议:          $scheme"
  echo "HTTP 状态码:   $code"
  echo "含 PRIMARY 模型: $(yn "$primary")"
  echo "含 FALLBACK 模型: $(yn "$fallback")"
  echo "耗时:          ${elapsed} ms"

  [[ "$code" == "200" && "$primary" == "1" && "$fallback" == "1" ]]
)
