import type { PageController } from '@page-agent/page-controller'

/** ponytail: page-agent has no stable selectorMap API — isolate all access here. */

export type SelectorMapNode = { ref?: Element }

export function readSelectorMap(pc: PageController): Map<number, SelectorMapNode> | undefined {
  const map = (pc as unknown as { selectorMap?: Map<number, SelectorMapNode> }).selectorMap
  return map?.size ? map : undefined
}

export function readElementTextMap(pc: PageController): Map<number, string> | undefined {
  return (pc as unknown as { elementTextMap?: Map<number, string> }).elementTextMap
}

export function entriesFromSelectorMap(pc: PageController): Array<{ index: number; element: Element }> {
  const map = readSelectorMap(pc)
  if (!map) return []
  return [...map.entries()]
    .filter(([, node]) => node.ref instanceof Element)
    .map(([index, node]) => ({ index, element: node.ref as Element }))
    .sort((a, b) => a.index - b.index)
}

export function elementFromSelectorMap(
  pc: PageController,
  index: number
): Element | undefined {
  return readSelectorMap(pc)?.get(index)?.ref
}

export function selectorEntriesFromMap(
  pc: PageController,
  fallback: () => Array<{ index: number; element: Element; title?: string }>
): Array<{ index: number; element: Element; title?: string }> {
  const map = readSelectorMap(pc)
  const textMap = readElementTextMap(pc)
  if (!map) return fallback()
  const entries: Array<{ index: number; element: Element; title?: string }> = []
  for (const [index, node] of map) {
    const ref = node?.ref
    if (ref) entries.push({ index, element: ref, title: textMap?.get(index) })
  }
  return entries.length ? entries : fallback()
}
