#!/usr/bin/env bash
# 把本目录装成 Hermes profile：~/.hermes/profiles/her-production
# 幂等：可重复跑；只覆盖 SOUL/profile.yaml/skills/scripts，不动 state/ runs/ .env。
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="${HERMES_PROFILE_DIR:-$HOME/.hermes/profiles/her-production}"

echo "install: $SRC -> $DST"
mkdir -p "$DST/skills" "$DST/scripts" "$DST/state"

cp "$SRC/SOUL.md" "$SRC/profile.yaml" "$DST/"
rsync -a --delete "$SRC/skills/" "$DST/skills/"
rsync -a --delete "$SRC/scripts/" "$DST/scripts/"
chmod +x "$DST/scripts/"*.sh

if [[ ! -f "$DST/config.yaml" ]]; then
  # key 不落 git：能从 coder 现配里同步 base_url/key 就同步，否则留 example 让用户填。
  coder_cfg="$HOME/.hermes/profiles/coder/config.yaml"
  cp "$SRC/config.yaml.example" "$DST/config.yaml"
  if [[ -f "$coder_cfg" ]]; then
    key="$(sed -n 's/^  api_key: \(sk-.*\)$/\1/p' "$coder_cfg" | head -1)"
    base="$(sed -n 's/^  base_url: \(.*\)$/\1/p' "$coder_cfg" | head -1)"
    if [[ -n "$key" && -n "$base" ]]; then
      sed -i '' -e "s|sk-请填你自己的网关key|$key|" -e "s|https://newapi.yuaiweiwu.com/v1|$base|" "$DST/config.yaml"
      echo "config.yaml: 已从 coder profile 同步网关 key/base_url"
    fi
  fi
fi

if [[ ! -f "$DST/.env" ]]; then
  cp "$SRC/.env.example" "$DST/.env"
  echo "⚠️  已生成 $DST/.env —— 填 HER_API_KEY 再跑产线（生图要它）。"
fi

echo "✅ 装好：$DST"
echo "跑法: hermes --profile her-production chat  （或 _hermes-cli.sh -p her-production chat -q '...' --oneshot -Q）"
