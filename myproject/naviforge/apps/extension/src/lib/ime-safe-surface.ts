const FOCUSABLE =
  'textarea, input, select, option, [contenteditable="true"], [contenteditable=""]'

const FOCUS_STEAL_CONTROLS = 'button, summary, a[href], [role="button"], [role="tab"]'

/** Chrome picks IME from html[lang] when focus moves — never set it on extension surfaces. */
export function guardDocumentLang(): () => void {
  const scrub = (): void => {
    document.documentElement.removeAttribute('lang')
    document.documentElement.removeAttribute('xml:lang')
  }
  scrub()
  const obs = new MutationObserver(() => scrub())
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['lang', 'xml:lang'] })
  return () => obs.disconnect()
}

/** True when mousedown should not move focus (avoids IME flips on incidental clicks). */
export function shouldPreventFocusSteal(target: EventTarget | null): boolean {
  if (!target || typeof (target as HTMLElement).closest !== 'function') return false
  const el = target as HTMLElement
  if (el.closest('[data-chat-selectable]')) return false
  if (el.closest('[data-ime-focus-ok]')) return false
  if (el.closest('[draggable="true"]')) return false
  if (el.closest(FOCUSABLE)) return false
  if (el.closest(FOCUS_STEAL_CONTROLS)) return true
  const active = document.activeElement
  if (active instanceof HTMLTextAreaElement && active.closest('[data-composer-input]')) {
    return true
  }
  return false
}

export function preventImeFocusSteal(event: {
  defaultPrevented: boolean
  target: EventTarget | null
  preventDefault(): void
}): void {
  if (event.defaultPrevented) return
  if (!shouldPreventFocusSteal(event.target)) return
  event.preventDefault()
}
