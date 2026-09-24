import type { DomSnapshot, SnapshotMode } from '@naviforge/dom-plane'

const DEFAULT_MAX_LINES = 80
const DEFAULT_MAX_CHARS = 12_000

export const SNAPSHOT_PROMPT_BUDGET: Record<SnapshotMode, { maxLines: number; maxChars: number }> = {
  compact: { maxLines: 40, maxChars: 6_000 },
  viewport: { maxLines: 80, maxChars: 12_000 },
  full: { maxLines: 200, maxChars: 24_000 },
}

/** Full-page interactive snapshots always start at page top — scrolling the viewport does not change them. */
export function isFullPageSnapshotHeader(header: string): boolean {
  return /\(full page\)/i.test(header)
}

export function snapshotTruncationHint(header: string): string {
  if (/\(viewport\)/i.test(header)) return 'use dom_scroll then dom_snapshot (viewport), or mode=full'
  return isFullPageSnapshotHeader(header)
    ? 'use dom_read({ "mode": "body" }) for article/README text, or dom_snapshot({ "mode": "viewport" })'
    : 'use dom_scroll then dom_snapshot'
}

export function snapshotPromptBudget(mode?: SnapshotMode): { maxLines: number; maxChars: number } {
  return mode ? SNAPSHOT_PROMPT_BUDGET[mode] : { maxLines: DEFAULT_MAX_LINES, maxChars: DEFAULT_MAX_CHARS }
}

/** Keep structural lines; drop `[N]...` rows whose index is not visible. */
export function filterSnapshotLinesByIndex(content: string, visible: ReadonlySet<number>): string {
  return content
    .split('\n')
    .filter((line) => {
      const match = /^\[(\d+)\]/.exec(line)
      return match ? visible.has(Number(match[1])) : true
    })
    .join('\n')
}

/** Trim snapshot body for LLM prompts; full snapshot remains in DomPlane for tools. */
export function compactSnapshotForPrompt(
  snap: DomSnapshot,
  opts?: { maxLines?: number; maxChars?: number }
): Pick<DomSnapshot, 'revision' | 'url' | 'title' | 'header' | 'content' | 'footer'> {
  const budget = snapshotPromptBudget(snap.mode)
  const maxLines = opts?.maxLines ?? budget.maxLines
  const maxChars = opts?.maxChars ?? budget.maxChars
  const lines = snap.content.split('\n')
  let content = lines.slice(0, maxLines).join('\n')
  if (lines.length > maxLines) {
    const hint = snapshotTruncationHint(snap.header)
    content += `\n… (${lines.length - maxLines} more lines — ${hint})`
  }
  if (content.length > maxChars) {
    content = `${content.slice(0, maxChars)}\n… (truncated)`
  }
  return { ...snap, content }
}
