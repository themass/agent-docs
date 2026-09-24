#!/usr/bin/env bash
# Verify Aliyun TTS proxy: health + OpenAI voice name mapping (ash → Ali NLS).
set -euo pipefail

URL="${ALI_TTS_PROXY_URL:-http://127.0.0.1:8969}"
HEALTH="${URL}/health"
SPEECH="${URL}/v1/audio/speech"

if ! curl -fsS -m 5 "$HEALTH" >/dev/null 2>&1; then
  echo "ali-tts-proxy: health check failed ($HEALTH)" >&2
  exit 1
fi

code=$(curl -sS -m 60 -o /dev/null -w '%{http_code}' -X POST "$SPEECH" \
  -H 'Content-Type: application/json' \
  -d '{"input":"GitHub Trending 今日前三名：LangChain、OpenHands、DeepAgents。","voice":"ash","model":"ali-tts","response_format":"mp3"}')

if [[ "$code" != "200" ]]; then
  echo "ali-tts-proxy: voice=ash synthesis returned HTTP $code (proxy missing OpenAI→Ali voice map?)" >&2
  exit 1
fi

echo "ali-tts-proxy: ok (health + ash voice map)"
