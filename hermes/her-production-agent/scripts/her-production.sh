#!/usr/bin/env bash
# her-production.sh — Her Production Agent 的唯一确定性执行通道。
# Agent（LLM）只允许经 terminal 调本脚本；产线状态在库里与产物里，不在对话里。
#
# 用法:
#   her-production.sh new   <workdir> --name 名字 [--asset 拉丁包名] [--tagline ..]
#                           [--personality ..] [--first-mes ..] [--prompt 生图提示词]
#                           [--renderer layered]
#   her-production.sh portrait <workdir>        # 生 portrait（newapi 豆包 seedream）
#   her-production.sh persona  <workdir>        # 装配+校验 V2 角色卡（persona 半）
#   her-production.sh pack     <workdir>        # 组装 asset pack + drill 写 ca_her_pack
#   her-production.sh verify   <workdir>        # 对账：读演练库打印 her 行
#   her-production.sh all      <workdir>        # portrait→persona→pack→verify
#
# 环境（<profile home>/.env，本脚本自动 source；见 .env.example）:
#   HER_API_BASE     默认 https://newapi.yuaiweiwu.com/v1
#   HER_API_KEY      网关 key（不落 git）
#   HER_IMAGE_MODEL  默认 doubao-seedream-5-0-flash
#   HER_DRILL_DB     演练 sqlite（默认 <profile>/state/drill.db）——只碰这里，永不碰生产。
#   HER_SERVER_REPO  server 仓库克隆（build_her_pack.py 所在）
#   HER_BASE_ZIP     现成已验收分层素材 zip（端上内置 demo-avatar-v1.zip）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
[[ -f "$PROFILE_HOME/.env" ]] && set -a && source "$PROFILE_HOME/.env" && set +a

HER_API_BASE="${HER_API_BASE:-https://newapi.yuaiweiwu.com/v1}"
HER_IMAGE_MODEL="${HER_IMAGE_MODEL:-doubao-seedream-5-0-flash}"
HER_DRILL_DB="${HER_DRILL_DB:-$PROFILE_HOME/state/drill.db}"
HER_SERVER_REPO="${HER_SERVER_REPO:-/Users/gqli/work/agent-docs-rolepack-20261127/myproject/companion-agent/server}"
HER_BASE_ZIP="${HER_BASE_ZIP:-/Users/gqli/work/myandroidTest/.claude/worktrees/focused-mclean-1bfa86/feature-companion/src/main/assets/avatars/demo-avatar-v1.zip}"

log()  { printf '\033[1;36m[her-prod]\033[0m %s\n' "$*"; }
ok()   { printf '✅ %s\n' "$*"; }
die()  { printf '\033[1;31m[her-prod] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }
need() { [[ -f "$1" ]] || die "缺少 $1 —— 先跑 her-production.sh new"; }

py_server() {  # 在 server 仓库的依赖环境里跑 python（build_her_pack 依赖 companion 包）
  ( cd "$HER_SERVER_REPO" && PYTHONPATH=src "uv" run --extra dev --extra livekit python "$@" )
}

cmd_new() {
  local wd="$1"; shift
  local name="" tagline="" personality="" first_mes="" prompt="" renderer="layered" asset=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) name="$2"; shift 2;;
      --tagline) tagline="$2"; shift 2;;
      --personality) personality="$2"; shift 2;;
      --first-mes) first_mes="$2"; shift 2;;
      --prompt) prompt="$2"; shift 2;;
      --renderer) renderer="$2"; shift 2;;
      --asset) asset="$2"; shift 2;;
      *) die "未知参数 $1";;
    esac
  done
  [[ -n "$name" ]] || die "--name 必填（brief 整理归 agent，脚本只接结构化字段）"
  # asset 名 = pack_id：小写 [a-z0-9_-]。中文名做不进 pack_id——agent 必须给 --asset。
  asset="$(echo "${asset:-$name}" | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9-' '-')"
  asset="$(echo "$asset" | sed -e 's/^-*//' -e 's/-$//')"
  [[ "$asset" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || die "asset/pack_id 不合法: '${asset:-（空）}'（要 [a-z0-9][a-z0-9_-]{0,63}，中文名必须 --asset 给拉丁名）"
  mkdir -p "$wd"
  jq -n --arg name "$name" --arg tagline "$tagline" --arg personality "$personality" \
        --arg first_mes "$first_mes" --arg prompt "${prompt:-portrait of $name, anime style, upper body, soft light}" \
        --arg renderer "$renderer" --arg asset "$asset" \
        '{name:$name, tagline:$tagline, personality:$personality, first_mes:$first_mes,
          image_prompt:$prompt, renderer:$renderer, asset:$asset, created_at:(now|todate)}' \
        > "$wd/brief.json"
  ok "brief: $wd/brief.json (asset=$asset renderer=$renderer)"
}

cmd_portrait() {
  local wd="$1"; need "$wd/brief.json"
  # 已有 portrait 默认复用：重跑不该换脸（换内容 = 顶 pack_version，那是刻意动作）。
  if [[ -f "$wd/portrait.png" && "${HER_PORTRAIT_FORCE:-0}" != 1 ]]; then
    ok "portrait: 复用 $wd/portrait.png（要重新生图：HER_PORTRAIT_FORCE=1）"
    return
  fi
  [[ -n "${HER_API_KEY:-}" ]] || die "HER_API_KEY 未配置（$PROFILE_HOME/.env，见 .env.example）"
  local prompt; prompt="$(jq -r .image_prompt "$wd/brief.json")"
  log "生 portrait: model=$HER_IMAGE_MODEL"
  local resp; resp="$(curl -sS -m 180 "$HER_API_BASE/images/generations" \
    -H "Authorization: Bearer $HER_API_KEY" -H "Content-Type: application/json" \
    -d "$(jq -n --arg m "$HER_IMAGE_MODEL" --arg p "$prompt" \
          '{model:$m, prompt:$p, n:1, size:"1024x1024"}')")"
  local url; url="$(echo "$resp" | jq -r '.data[0].url // .data[0].b64_json // empty')"
  [[ -n "$url" ]] || die "生图失败: $(echo "$resp" | head -c 400)"
  # 生图产物是不可信外部字节：先落 workdir，验明确是图片才认。
  if [[ "${url:0:5}" == "http:" || "${url:0:6}" == "https:" ]]; then
    curl -sS -m 120 -o "$wd/portrait.raw" "$url"
  else
    echo "$resp" | jq -r '.data[0].b64_json' | base64 -d > "$wd/portrait.raw"
  fi
  file "$wd/portrait.raw" | grep -qi 'PNG\|JPEG' || die "产物不是图片: $(file -b "$wd/portrait.raw")"
  mv "$wd/portrait.raw" "$wd/portrait.png"
  ok "portrait: $wd/portrait.png ($(wc -c < "$wd/portrait.png" | tr -d ' ') bytes)"
}

cmd_persona() {
  local wd="$1"; need "$wd/brief.json"
  # 装配 V2 卡；model_ref 用桥形态 {renderer,asset}（与 seed_from_cards 同口径）。
  # 位置按 card.from_v2_json 的读法：data.model_ref 顶层（extensions.model_ref 它不读）。
  jq '{spec:"chara_card_v2", spec_version:"2.0", data:{
        name:.name, description:.personality, personality:.personality,
        first_mes:(.first_mes // ""), mes_example:"",
        creator_notes:"generated by her-production agent (drill)",
        character_version:"0.1.0", tags:["hermes-drill"],
        model_ref:{renderer:.renderer, asset:.asset},
        tagline:.tagline}}' "$wd/brief.json" > "$wd/character.v2.json"
  # persona 半必须过现成卡校验（from_v2_json）——装配错误在产线内炸，不进库。
  py_server -c '
import json, sys
from companion.agent.roles.card import from_v2_json
card = from_v2_json(json.load(open(sys.argv[1])))
assert card.name and card.model_ref, "card missing name/model_ref"
print("validated:", card.name, card.model_ref)
' "$wd/character.v2.json" || die "V2 卡校验失败"
  ok "persona: $wd/character.v2.json"
}

cmd_pack() {
  local wd="$1"; need "$wd/brief.json"; need "$wd/portrait.png"
  [[ -f "$HER_BASE_ZIP" ]] || die "现成素材 zip 不存在: $HER_BASE_ZIP"
  local asset renderer name tagline
  asset="$(jq -r .asset "$wd/brief.json")"; renderer="$(jq -r .renderer "$wd/brief.json")"
  name="$(jq -r .name "$wd/brief.json")";   tagline="$(jq -r .tagline "$wd/brief.json")"
  local stage="$wd/pack-src"; rm -rf "$stage"; mkdir -p "$stage" "$wd/out"
  # 已验收的分层素材为底（真文件），portrait 进包当 thumbnail 文件。
  unzip -q "$HER_BASE_ZIP" -d "$stage"
  cp "$wd/portrait.png" "$stage/portrait.png"
  # G-A 门 + upsert + bind + invalidate 全在 build_her_pack.py 里（M0 链，已 24 测试钉死）。
  COMPANION_DATABASE_URL="sqlite+aiosqlite:///$HER_DRILL_DB" \
    py_server tools/build_her_pack.py \
      --assets-dir "$stage" --pack-id "$asset" --renderer "$renderer" \
      --entry-point manifest.json --out "$wd/out" \
      --name "$name" --tagline "$tagline" \
      --cdn-base "${HER_CDN_BASE:-https://cdn.invalid/drill}" \
      --role-id "$asset" | tee "$wd/pack.log"
  grep -q "her pack:" "$wd/pack.log" || die "pack/deploy 失败（见 $wd/pack.log）"
  ok "pack: $wd/out/$asset-v1.zip + ca_her_pack 演练行"
}

cmd_verify() {
  local wd="$1"; need "$wd/brief.json"
  local asset renderer
  asset="$(jq -r .asset "$wd/brief.json")"; renderer="$(jq -r .renderer "$wd/brief.json")"
  # 对账走 M0 测试同一条读链：store.load（ca_her_pack 行）+ default 绑定。
  py_server -c '
import asyncio, json, sys
from sqlalchemy.ext.asyncio import create_async_engine
from companion.service.roles.hers import SqlHerPackStore

async def main(url, her_id, role_id):
    eng = create_async_engine(url)
    store = SqlHerPackStore(eng)
    rec = await store.load(her_id)
    assert rec is not None, f"no row for {her_id}"
    default = await store.default_her_id(role_id)
    print(json.dumps({"her_id": rec.her_id, "pack_version": rec.pack_version,
                      "status": rec.status, "source": rec.source,
                      "bound_default": default,
                      "model_ref": rec.payload["model_ref"]},
                     ensure_ascii=False, indent=1))
    await eng.dispose()

asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
' "sqlite+aiosqlite:///$HER_DRILL_DB" "$renderer-$asset" "$asset" \
    || die "对账失败：演练库里没有 $renderer-$asset"
  ok "verify: $renderer-$asset 在演练库 ca_her_pack + 默认可见"
}

cmd_all() {
  local wd="$1"
  cmd_portrait "$wd"; cmd_persona "$wd"; cmd_pack "$wd"; cmd_verify "$wd"
}

# workdir 一律绝对化：py_server 会 cd 进 server 仓库，相对路径会断。
SUB="${1:-help}"; shift || true
if [[ "$SUB" != help && $# -gt 0 && "${1:0:1}" != "/" ]]; then
  set -- "$PWD/$1" "${@:2}"
fi

case "$SUB" in
  new)      cmd_new "$@";;
  portrait) cmd_portrait "$@";;
  persona)  cmd_persona "$@";;
  pack)     cmd_pack "$@";;
  verify)   cmd_verify "$@";;
  all)      cmd_all "$@";;
  *) cat <<'EOF'
用法: her-production.sh {new|portrait|persona|pack|verify|all} <workdir> [...]
详见脚本头部注释。
EOF
     exit 2;;
esac
