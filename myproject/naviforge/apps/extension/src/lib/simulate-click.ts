function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function scrollIntoViewIfNeeded(element: Element): void {
  const rect = element.getBoundingClientRect()
  const inView =
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <= window.innerHeight &&
    rect.right <= window.innerWidth
  if (!inView) {
    element.scrollIntoView({ block: 'center', inline: 'center', behavior: 'auto' })
  }
}

/** Temporarily disable agent overlays so elementFromPoint hits the real target. */
function withPassThrough<T>(fn: () => T): T {
  const blocked = [
    ...document.querySelectorAll(
      '#playwright-highlight-container, #naviforge-mark-layer, [data-naviforge-overlay], [data-page-agent-ignore="true"]'
    ),
  ] as HTMLElement[]
  const prev = blocked.map((el) => el.style.pointerEvents)
  for (const el of blocked) el.style.pointerEvents = 'none'
  try {
    return fn()
  } finally {
    blocked.forEach((el, index) => {
      el.style.pointerEvents = prev[index] ?? ''
    })
  }
}

let lastClicked: HTMLElement | null = null

function blurLastClicked(): void {
  if (!lastClicked) return
  lastClicked.dispatchEvent(new PointerEvent('pointerout', { bubbles: true }))
  lastClicked.dispatchEvent(new PointerEvent('pointerleave', { bubbles: false }))
  lastClicked.dispatchEvent(new MouseEvent('mouseout', { bubbles: true }))
  lastClicked.dispatchEvent(new MouseEvent('mouseleave', { bubbles: false }))
  lastClicked.blur()
  lastClicked = null
}

async function dispatchClickAt(doc: Document, x: number, y: number, preferred?: HTMLElement): Promise<HTMLElement | null> {
  await wait(50)

  const hitTarget = withPassThrough(() => doc.elementFromPoint(x, y))
  const target =
    preferred &&
    hitTarget instanceof HTMLElement &&
    (preferred.contains(hitTarget) || preferred === hitTarget)
      ? hitTarget
      : hitTarget instanceof HTMLElement
        ? hitTarget
        : preferred ?? null

  if (!target) return null

  blurLastClicked()
  lastClicked = target

  const pointerOpts: PointerEventInit = {
    bubbles: true,
    cancelable: true,
    clientX: x,
    clientY: y,
    pointerType: 'mouse',
    isPrimary: true,
    button: 0,
    buttons: 1,
  }
  const mouseOpts: MouseEventInit = { bubbles: true, cancelable: true, clientX: x, clientY: y, button: 0 }

  target.dispatchEvent(new PointerEvent('pointerover', pointerOpts))
  target.dispatchEvent(new PointerEvent('pointerenter', { ...pointerOpts, bubbles: false }))
  target.dispatchEvent(new MouseEvent('mouseover', mouseOpts))
  target.dispatchEvent(new MouseEvent('mouseenter', { ...mouseOpts, bubbles: false }))
  target.dispatchEvent(new PointerEvent('pointerdown', pointerOpts))
  target.dispatchEvent(new MouseEvent('mousedown', mouseOpts))
  if (typeof target.focus === 'function') target.focus({ preventScroll: true })
  target.dispatchEvent(new PointerEvent('pointerup', pointerOpts))
  target.dispatchEvent(new MouseEvent('mouseup', mouseOpts))
  target.dispatchEvent(new MouseEvent('click', mouseOpts))
  target.click()
  await wait(80)
  return target
}

/** Pagenter-style thick click: scroll, pointer chain, passThrough hit-test, native click. */
export async function simulateClickElement(element: HTMLElement): Promise<void> {
  const frame = element.ownerDocument.defaultView?.frameElement
  scrollIntoViewIfNeeded(element)
  if (frame instanceof HTMLElement) scrollIntoViewIfNeeded(frame)

  const rect = element.getBoundingClientRect()
  const x = rect.left + rect.width / 2
  const y = rect.top + rect.height / 2
  await dispatchClickAt(element.ownerDocument, x, y, element)
}

/**
 * Screenshot / vision coordinate click in the top document viewport.
 * Coordinates are CSS pixels relative to the viewport (same as elementFromPoint).
 */
export async function simulateClickAt(
  x: number,
  y: number,
  root: Document = document
): Promise<{ ok: true; tag: string } | { ok: false; error: string }> {
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return { ok: false, error: 'x and y must be finite numbers' }
  }
  const target = await dispatchClickAt(root, x, y)
  if (!target) return { ok: false, error: `no element at (${x}, ${y})` }
  return { ok: true, tag: target.tagName.toLowerCase() }
}
