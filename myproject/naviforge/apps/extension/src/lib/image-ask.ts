/** Raster images only — SVG is not a screenshot and can be huge/scripted. */
export const IMAGE_FILE_RE = /\.(png|jpe?g|webp|gif)$/i

export const MAX_IMAGE_BYTES = 8 * 1024 * 1024

export const IMAGE_ASK_DEFAULT_QUESTION = '描述这张图里可见的内容，看不清的如实说明。'

export type ShotAskRef = { kind: 'path'; path: string } | { kind: 'latest' }

/** User wants a new capture / agent loop, not one-shot vision on an existing image. */
const TAKE_SHOT =
  /帮我截图|再截一张|截一张|截个图|全页截图|滚动截图|take a screenshot|screenshot (the|this) page/i

/** Mentions an existing shot (workspace or “the one just now”). */
const LOOK_SHOT =
  /刚才的截图|上次(的)?截图|这张截图|那张截图|看看截图|看一下截图|截图里|截图中|截图上|分析.{0,12}截图|截图.{0,8}(是什么|有什么|多少|手机号|写了)|previous screenshot|last screenshot|that screenshot|the screenshot/i

function shotPathsIn(text: string): string[] {
  const matches = text.match(/shots\/[^\s（）)\]"'{}<>]+/g) ?? []
  return [...new Set(matches.map((path) => path.replace(/[,.;]+$/, '')))].filter((path) =>
    IMAGE_FILE_RE.test(path)
  )
}

export function isAllowedImageFile(file: { name: string; type: string; size: number }): boolean {
  if (file.size <= 0 || file.size > MAX_IMAGE_BYTES) return false
  if (/^image\/svg/i.test(file.type) || /\.svg$/i.test(file.name)) return false
  if (/^image\/(png|jpeg|webp|gif)$/i.test(file.type)) return true
  return IMAGE_FILE_RE.test(file.name)
}

/** Route composer text to lane A (existing image) vs B (agent). Null = not A. */
export function shotAskFromText(text: string): ShotAskRef | null {
  const trimmed = text.trim()
  if (!trimmed || TAKE_SHOT.test(trimmed)) return null
  const path = shotPathsIn(trimmed)[0]
  if (path) return { kind: 'path', path }
  if (LOOK_SHOT.test(trimmed)) return { kind: 'latest' }
  return null
}
