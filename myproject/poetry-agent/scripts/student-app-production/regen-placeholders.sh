#!/usr/bin/env bash
# 重新生成《春望》全部占位素材并登记(生产动作,不是测试)。需要:node、ffmpeg/ffprobe、macOS say、本机 Chrome、cwebp。
# 缺任何一个会明确报错退出,不会静默生成空文件。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
P="$ROOT/student-app/production"
node "$P/tools/prod.mjs" gen chun-wang
node "$P/tools/gen/gen-character-dufu.mjs"
node "$P/tools/character-check.mjs" "$P/published/characters/du-fu/manifest.json"
node "$P/tools/register-character.mjs" "$P/published/characters/du-fu" --prefix a-dufu --step meet
node "$P/tools/gen/gen-chun-wang-text.mjs"
node "$P/tools/gen/gen-chun-wang-scene.mjs"
node "$P/tools/gen/gen-chun-wang-audio.mjs"
node "$P/tools/prod.mjs" placeholder chun-wang
node "$P/tools/prod.mjs" registry-check
node "$P/tools/prod.mjs" bundle-refs chun-wang
node "$P/tools/prod.mjs" gen chun-wang
