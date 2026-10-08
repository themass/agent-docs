import path from 'node:path'
import { chmod, writeFile } from 'node:fs/promises'

export const DOWNLOAD_HLS_SH = `#!/usr/bin/env bash
# NaviForge — download HLS (m3u8) with ffmpeg. Usage:
#   ./download-hls.sh '<m3u8-or-master-url>' [output.mp4]
set -euo pipefail
URL="\${1:?m3u8 URL required}"
OUT="\${2:-output.mp4}"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Install ffmpeg first (brew install ffmpeg)" >&2
  exit 1
fi
ffmpeg -y -i "$URL" -c copy -bsf:a aac_adtstoasc "$OUT"
echo "Saved: $OUT"
`

export async function seedDefaultScripts(scriptsDir: string): Promise<void> {
  const target = path.join(scriptsDir, 'download-hls.sh')
  try {
    await writeFile(target, DOWNLOAD_HLS_SH, { encoding: 'utf8', flag: 'wx' })
    await chmod(target, 0o755)
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code
    if (code !== 'EEXIST') throw error
  }
}
