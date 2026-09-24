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

/** Resolve frame path like "f0" to document for element lookup. */
export function documentForFramePath(path: string | undefined, root: Document = document): Document {
  if (!path?.startsWith('f')) return root
  const index = Number.parseInt(path.slice(1), 10)
  if (!Number.isFinite(index)) return root
  const frame = root.querySelectorAll('iframe')[index]
  try {
    return frame?.contentDocument ?? root
  } catch {
    return root
  }
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
