#!/usr/bin/env bash
# 把《春望》已登记真实定位的来源提交核验（走 Studio 的 verifySource，不直接改库）。
#
# 为什么走接口而不是 SQL：verifySource 会过发布门禁、跑完整性审计、写评审日志。直接 UPDATE
# verification_status 会绕过这三样，之后的发布审计会在毫无提示的情况下失败。
#
# 前置：V010、V011 已在目标库执行；宿主已配置 poetry.studioReviewerToken。
#
# 用法：
#   POETRY_STUDIO_REVIEWER_TOKEN=... POETRY_API_BASE_URL=http://127.0.0.1:8080 ./scripts/db/verify-sources.sh          # 只列出要做什么
#   POETRY_STUDIO_REVIEWER_TOKEN=... POETRY_API_BASE_URL=http://127.0.0.1:8080 ./scripts/db/verify-sources.sh --apply  # 真的提交
#
# 令牌只从环境变量读，并通过 stdin 交给 curl（命令行参数在 ps 里看得到，stdin 看不到）；脚本不打印它。
#
# 只核验这两个来源。新唐书（source-dufu-zhuan-candidate）**故意不在列表里**：它还被「杜甫生卒 712–770」这条
# claim 引用，而那条的定位仍是占位，两部史书都不能支持它；verifySource 会以 LOCATOR_MISSING 拒绝，这是对的。
set -euo pipefail

BASE="${POETRY_API_BASE_URL:-}"
TOKEN="${POETRY_STUDIO_REVIEWER_TOKEN:-}"
[[ -n "$BASE" ]]  || { echo "需要 POETRY_API_BASE_URL（例如 http://127.0.0.1:8080）" >&2; exit 2; }
APPLY=0
case "${1:-}" in
  --apply) APPLY=1 ;;
  "") ;;
  *) echo "用法: $0 [--apply]" >&2; exit 2 ;;
esac
if [[ "$APPLY" == 1 ]]; then
  [[ -n "$TOKEN" ]] || { echo "需要 POETRY_STUDIO_REVIEWER_TOKEN" >&2; exit 2; }
fi

# 来源 id | 这次核对了什么（写进评审日志）
SOURCES=(
  "source-quantangshi-224|AI 对照核对：库内 8 句与维基文库《全唐詩》卷224、chinese-poetry 全唐诗/御定全唐詩卷224 三处逐字一致（繁→简后）；作者归属引文见 poetry_citation。"
  "source-jiutangshu-dufu|AI 对照核对：引文取自维基文库《舊唐書》卷190下杜甫传，逐字摘录含异体字；注意该页面标注未校对，正式发布前建议再对影印本。只支持「禄山陷京师/甫自京师宵遁」，不支持写作年份与生卒年。"
)

for entry in "${SOURCES[@]}"; do
  id="${entry%%|*}"; note="${entry#*|}"
  if [[ "$APPLY" == 0 ]]; then
    printf '将核验  %s\n        %s\n' "$id" "$note"
    continue
  fi
  body=$(python3 - "$note" <<'PY'
import json, sys
print(json.dumps({"decision": "VERIFY", "reviewer": "ai-content-review",
                  "reviewer_role": "PLATFORM_ADMIN", "note": sys.argv[1]}, ensure_ascii=False))
PY
)
  printf '核验    %s ... ' "$id"
  # curl 配置从 stdin 读：令牌不会出现在进程列表里。
  http=$(printf 'header = "X-Poetry-Studio-Reviewer-Token: %s"\n' "$TOKEN" | curl -sS -K - \
      -o /tmp/verify-source.out -w '%{http_code}' \
      -X POST "$BASE/api/poetry/v1/studio/sources/$id/verification" \
      -H 'Content-Type: application/json' --data "$body" || true)
  echo "HTTP $http"
  # 响应体只在失败时打印，且不含令牌；成功时的审计明细也在里面，留给人看。
  if [[ "$http" != 200 ]]; then cat /tmp/verify-source.out; echo; fi
done
[[ "$APPLY" == 1 ]] || echo "（以上只是列出。加 --apply 才会真的提交。）"
