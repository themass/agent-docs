const INTERACTIVE = 'a,button,input,textarea,select,[role="button"],[role="link"]'
const MAX_FRAME_LINES = 40
const MAX_SHADOW_LINES = 20

function labelFor(element: Element): string {
  const text =
    element.getAttribute('aria-label') ||
    (element instanceof HTMLInputElement ? element.placeholder : '') ||
    element.textContent?.trim().slice(0, 80) ||
    element.tagName.toLowerCase()
  return text.replace(/\s+/g, ' ')
}

/** Collect same-origin iframe and open-shadow interactive hints for snapshot supplement. */
export function collectFrameSupplement(root: Document = document): string {
  const lines: string[] = []

  const iframes = [...root.querySelectorAll('iframe')]
  iframes.slice(0, 8).forEach((frame, index) => {
    const src = frame.getAttribute('src') || 'about:blank'
    try {
      const inner = frame.contentDocument
      if (!inner) {
        lines.push(`[frame f${index}] cross-origin src=${src}`)
        return
      }
      lines.push(`[frame f${index}] src=${src}`)
      const items = [...inner.querySelectorAll(INTERACTIVE)].slice(0, 6)
      for (const item of items) {
        lines.push(`  [f${index}] ${item.tagName.toLowerCase()} "${labelFor(item)}"`)
      }
    } catch {
      lines.push(`[frame f${index}] cross-origin src=${src}`)
    }
  })

  let shadowCount = 0
  const visit = (node: Element) => {
    if (shadowCount >= MAX_SHADOW_LINES) return
    const shadow = node.shadowRoot
    if (shadow) {
      const host = node.tagName.toLowerCase()
      const items = [...shadow.querySelectorAll(INTERACTIVE)].slice(0, 4)
      for (const item of items) {
        lines.push(`[shadow ${host}] ${item.tagName.toLowerCase()} "${labelFor(item)}"`)
        shadowCount += 1
        if (shadowCount >= MAX_SHADOW_LINES) break
      }
    }
    for (const child of node.children) visit(child)
  }
  visit(root.documentElement)

  return lines.slice(0, MAX_FRAME_LINES).join('\n')
}

export type FrameHop = { index: number; token: string }

export type FrameResolveOk = { ok: true; document: Document; hops: FrameHop[] }
export type FrameResolveErr = {
  ok: false
  code: 'bad_path' | 'not_found' | 'cross_origin'
  error: string
  hops: FrameHop[]
}
export type FrameResolveResult = FrameResolveOk | FrameResolveErr

/**
 * Parse Playwright-style frame hops: `f0`, `f0>>f1`, `f1>>f0>>f2`.
 * Returns null when the path is empty or malformed.
 */
export function parseFrameHops(path: string | undefined): FrameHop[] | null {
  if (!path?.trim()) return []
  const raw = path.trim()
  const parts = raw.split('>>').map((part) => part.trim()).filter(Boolean)
  if (!parts.length) return null
  const hops: FrameHop[] = []
  for (const token of parts) {
    const match = /^f(\d+)$/i.exec(token)
    if (!match) return null
    hops.push({ token: token.toLowerCase(), index: Number.parseInt(match[1]!, 10) })
  }
  return hops
}

/**
 * Resolve a frame path with `>>` hops. Cross-origin frames fail loudly —
 * never silently fall back to the main document (that caused wrong-element clicks).
 */
export function resolveLocatorWithHops(
  path: string | undefined,
  root: Document = document
): FrameResolveResult {
  const hops = parseFrameHops(path)
  if (hops === null) {
    return { ok: false, code: 'bad_path', error: `invalid framePath: ${path}`, hops: [] }
  }
  if (!hops.length) return { ok: true, document: root, hops }

  let current = root
  for (const hop of hops) {
    const frames = current.querySelectorAll('iframe')
    const frame = frames[hop.index]
    if (!frame) {
      return {
        ok: false,
        code: 'not_found',
        error: `frame ${hop.token} not found (have ${frames.length})`,
        hops,
      }
    }
    try {
      const inner = frame.contentDocument
      if (!inner) {
        const src = frame.getAttribute('src') || 'about:blank'
        return {
          ok: false,
          code: 'cross_origin',
          error: `frame ${hop.token} is cross-origin (src=${src}); cannot click inside`,
          hops,
        }
      }
      current = inner
    } catch {
      const src = frame.getAttribute('src') || 'about:blank'
      return {
        ok: false,
        code: 'cross_origin',
        error: `frame ${hop.token} is cross-origin (src=${src}); cannot click inside`,
        hops,
      }
    }
  }
  return { ok: true, document: current, hops }
}

/**
 * @deprecated Prefer resolveLocatorWithHops — this helper returns null on any
 * frame failure so callers never silently act on the main document.
 */
export function documentForFramePath(
  path: string | undefined,
  root: Document = document
): Document | null {
  const resolved = resolveLocatorWithHops(path, root)
  return resolved.ok ? resolved.document : null
}

/** Wait until DOM mutations settle (MutationObserver quiet window). */
export function waitForStableDom(
  timeoutMs: number,
  quietMs = 500
): Promise<{ ok: true } | { ok: false; error: string }> {
  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs
    let quietTimer: number | undefined

    const finish = (ok: boolean) => {
      observer.disconnect()
      if (quietTimer) window.clearTimeout(quietTimer)
      window.clearTimeout(hardTimer)
      resolve(ok ? { ok: true } : { ok: false, error: 'wait stable timeout' })
    }

    // A page that never mutates and never reaches `complete` would otherwise
    // leave this promise pending forever, hanging the caller's tool call.
    const hardTimer = window.setTimeout(() => finish(false), timeoutMs)

    const observer = new MutationObserver(() => {
      if (quietTimer) window.clearTimeout(quietTimer)
      if (Date.now() >= deadline) {
        finish(false)
        return
      }
      quietTimer = window.setTimeout(() => finish(true), quietMs)
    })

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
    })

    quietTimer = window.setTimeout(() => {
      if (document.readyState === 'complete') finish(true)
    }, quietMs)
  })
}
