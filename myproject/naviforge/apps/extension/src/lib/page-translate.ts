/**
 * In-page translation for Toolkit — stay on the same tab URL.
 * Chrome does not expose the native right-click "Translate to 中文" API, so we
 * rewrite visible text nodes in place (second run restores the original).
 */

export type PageTranslateResult = {
  ok: boolean
  mode?: 'restore' | 'gtx'
  translated?: number
  /** `true` when the page had more text nodes than the bounded translation pass. */
  limited?: boolean
  error?: string
  lang?: string
}

type CollectResult =
  | { restored: true; count: number }
  | { restored: false; texts: string[]; limited: boolean }

export const TRANSLATE_LANGS = [
  { id: 'zh-CN', label: '中文' },
  { id: 'en', label: 'English' },
  { id: 'ja', label: '日本語' },
  { id: 'ko', label: '한국어' },
] as const

export type TranslateLangId = (typeof TRANSLATE_LANGS)[number]['id']

export function translateLangLabel(id: string): string {
  return TRANSLATE_LANGS.find((item) => item.id === id)?.label ?? id
}

export function isTranslateLangId(value: string): value is TranslateLangId {
  return TRANSLATE_LANGS.some((item) => item.id === value)
}

export function formatTranslationFeedback(
  result: Pick<PageTranslateResult, 'mode' | 'translated' | 'limited'> & { lang?: string }
): string {
  if (result.mode === 'restore') return `已还原原文（${result.translated ?? 0} 处）`
  const translated = result.translated ?? 0
  const lang = translateLangLabel(result.lang ?? 'zh-CN')
  return result.limited
    ? `已译成${lang}（${translated} 处，仅前 500 段；再运行一次还原）`
    : `已译成${lang}（${translated} 处；再运行一次还原）`
}

/** Collect text nodes or restore a previous in-page translation. Runs in the page. */
export function collectOrRestorePageText(): CollectResult {
  const skip = new Set([
    'SCRIPT',
    'STYLE',
    'NOSCRIPT',
    'TEXTAREA',
    'INPUT',
    'SELECT',
    'CODE',
    'PRE',
    'KBD',
    'SAMP',
    'SVG',
    'MATH',
    'IFRAME',
  ])
  const win = window as Window & {
    __naviforgeTranslateBackup?: Array<[Text, string]>
    __naviforgeTranslateNodes?: Text[]
  }
  if (win.__naviforgeTranslateBackup?.length) {
    let count = 0
    for (const [node, text] of win.__naviforgeTranslateBackup) {
      if (node.isConnected) {
        node.nodeValue = text
        count += 1
      }
    }
    win.__naviforgeTranslateBackup = undefined
    win.__naviforgeTranslateNodes = undefined
    document.documentElement.removeAttribute('data-naviforge-translated')
    return { restored: true, count }
  }

  const nodes: Text[] = []
  const texts: string[] = []
  if (!document.body) return { restored: false, texts: [], limited: false }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement
      if (!parent || skip.has(parent.tagName)) return NodeFilter.FILTER_REJECT
      if (
        parent.closest(
          '[contenteditable="true"], [data-naviforge-translate-skip], #naviforge-translate-hud, #naviforge-ocr-hud, [data-naviforge-crop]'
        )
      ) {
        return NodeFilter.FILTER_REJECT
      }
      const value = node.nodeValue ?? ''
      if (!value.trim()) return NodeFilter.FILTER_REJECT
      if (value.length > 2_000) return NodeFilter.FILTER_REJECT
      return NodeFilter.FILTER_ACCEPT
    },
  })
  let current = walker.nextNode()
  while (current && nodes.length < 500) {
    nodes.push(current as Text)
    texts.push((current as Text).nodeValue ?? '')
    current = walker.nextNode()
  }
  win.__naviforgeTranslateNodes = nodes
  return { restored: false, texts, limited: current !== null }
}

/** Apply translated strings to previously collected text nodes. Runs in the page. */
export function applyPageTranslations(translated: string[]): number {
  const win = window as Window & {
    __naviforgeTranslateBackup?: Array<[Text, string]>
    __naviforgeTranslateNodes?: Text[]
  }
  const nodes = win.__naviforgeTranslateNodes ?? []
  const backup: Array<[Text, string]> = []
  let count = 0
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index]
    const next = translated[index]
    if (!node?.isConnected || next == null) continue
    backup.push([node, node.nodeValue ?? ''])
    node.nodeValue = next
    count += 1
  }
  win.__naviforgeTranslateBackup = backup
  document.documentElement.setAttribute('data-naviforge-translated', '1')
  return count
}

async function translateChunkGtx(text: string, targetLang: string): Promise<string> {
  if (!text.trim()) return text
  const url =
    `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${encodeURIComponent(targetLang)}` +
    `&dt=t&q=${encodeURIComponent(text.slice(0, 4500))}`
  const response = await fetch(url)
  if (!response.ok) throw new Error(`translate HTTP ${response.status}`)
  const data = (await response.json()) as unknown
  if (!Array.isArray(data) || !Array.isArray(data[0])) throw new Error('unexpected translate payload')
  return (data[0] as unknown[])
    .map((part) => (Array.isArray(part) && typeof part[0] === 'string' ? part[0] : ''))
    .join('')
}

/** Batch translate with limited concurrency (extension process / Host permissions). */
export async function translateTextsGtx(texts: string[], targetLang: string): Promise<string[]> {
  const out = texts.slice()
  const pending: number[] = []
  for (let index = 0; index < texts.length; index += 1) {
    if (texts[index]!.trim()) pending.push(index)
  }
  const concurrency = 6
  let cursor = 0
  async function worker(): Promise<void> {
    while (cursor < pending.length) {
      const index = pending[cursor]!
      cursor += 1
      out[index] = await translateChunkGtx(texts[index]!, targetLang)
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, pending.length || 1) }, () => worker()))
  return out
}

async function showTranslateHud(
  tabId: number,
  title: string,
  body: string,
  sticky = false
): Promise<void> {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (heading: string, detail: string, keep: boolean) => {
        const id = 'naviforge-translate-hud'
        document.getElementById(id)?.remove()
        const root = document.createElement('div')
        root.id = id
        root.setAttribute('role', 'status')
        Object.assign(root.style, {
          position: 'fixed',
          zIndex: '2147483647',
          top: '16px',
          right: '16px',
          width: 'min(360px, calc(100vw - 32px))',
          padding: '12px 14px',
          background: '#111',
          color: '#fff',
          font: '13px/1.45 system-ui,sans-serif',
          borderRadius: '10px',
          boxShadow: '0 8px 24px rgba(0,0,0,.28)',
        })
        const titleEl = document.createElement('div')
        titleEl.style.fontWeight = '650'
        titleEl.textContent = heading
        const bodyEl = document.createElement('div')
        bodyEl.style.margin = '6px 0 0'
        bodyEl.style.color = '#ddd'
        bodyEl.textContent = detail
        root.append(titleEl, bodyEl)
        if (keep) {
          const close = document.createElement('button')
          close.type = 'button'
          close.textContent = '关闭'
          Object.assign(close.style, {
            marginTop: '10px',
            border: '0',
            borderRadius: '6px',
            padding: '6px 10px',
            background: '#333',
            color: '#fff',
            font: '650 12px system-ui',
            cursor: 'pointer',
          })
          close.addEventListener('click', () => root.remove())
          root.append(close)
        }
        document.documentElement.appendChild(root)
        if (!keep) setTimeout(() => root.remove(), 8000)
      },
      args: [title, body, sticky],
    })
  } catch {
    // restricted page
  }
}

/**
 * Translate the bound tab in place (toggle restores original text).
 * Does not open a new tab or change the page URL.
 */
export async function translateTabInPlace(
  tabId: number,
  targetLang = 'zh-CN'
): Promise<PageTranslateResult> {
  const lang = translateLangLabel(targetLang)
  await showTranslateHud(tabId, '正在翻译', `正在把本页译成${lang}…`, true)
  try {
    const [injection] = await chrome.scripting.executeScript({
      target: { tabId },
      func: collectOrRestorePageText,
    })
    const collected = injection?.result as CollectResult | undefined
    if (!collected) {
      await showTranslateHud(tabId, '翻译失败', '无法读取页面文本', true)
      return { ok: false, error: '无法读取页面文本' }
    }
    if (collected.restored) {
      const message = formatTranslationFeedback({
        mode: 'restore',
        translated: collected.count,
      })
      await showTranslateHud(tabId, '已还原原文', message, true)
      return { ok: true, mode: 'restore', translated: collected.count }
    }

    const { texts, limited } = collected
    if (!texts.length) {
      await showTranslateHud(tabId, '翻译失败', '当前页没有可翻译的文本（图片、视频、iframe 里的字读不到）', true)
      return { ok: false, error: '当前页没有可翻译的文本' }
    }

    await showTranslateHud(tabId, '正在翻译', `正在译成${lang}（${texts.length} 段，可能要几秒）…`, true)
    const translated = await translateTextsGtx(texts, targetLang)
    const [applied] = await chrome.scripting.executeScript({
      target: { tabId },
      func: applyPageTranslations,
      args: [translated],
    })
    const result: PageTranslateResult = {
      ok: true,
      mode: 'gtx',
      translated: typeof applied?.result === 'number' ? applied.result : translated.length,
      limited,
      lang: targetLang,
    }
    await showTranslateHud(tabId, `已译成${lang}`, formatTranslationFeedback(result), true)
    return result
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    await showTranslateHud(tabId, '翻译失败', message, true)
    return { ok: false, error: message }
  }
}
