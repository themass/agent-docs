/** Best-effort readable label for an element, used by the picker and DOM extract. */
export function titleForElement(element: Element): string {
  const aria = element.getAttribute('aria-label')?.trim()
  if (aria && aria.length >= 2) return aria.slice(0, 160)
  const title = element.getAttribute('title')?.trim()
  if (title && title.length >= 2) return title.slice(0, 160)
  const text = (element.textContent ?? '').replace(/\s+/g, ' ').trim()
  return text.slice(0, 160)
}
