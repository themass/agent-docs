import type { DomSnapshot } from '@naviforge/dom-plane'

const NOISE =
  /^(登录|注册|sign in|home|\*{3}|\.{3}|axx\.|http|www\.|当前页|Start of page|End of page|\[\d+\])/i

/** Titles / labels visible in snapshot text but missing from structured extract (SPA feeds). */
export function extractFeedLabelsFromSnapshot(snap: DomSnapshot, limit = 24): string[] {
  const blob = [snap.header, snap.content, snap.footer].filter(Boolean).join('\n')
  const lines = blob
    .split(/\n+/)
    .map((line) => line.replace(/\*\[\d+\]/g, '').trim())
    .filter((line) => line.length >= 3 && line.length <= 120)
  const out: string[] = []
  const seen = new Set<string>()
  for (const line of lines) {
    if (NOISE.test(line)) continue
    if (!/[\u4e00-\u9fffA-Za-z0-9]/.test(line)) continue
    if (/^(热销|限时|热门|专题|专区)/.test(line) && line.length < 12) continue
    if (/^(热销|限时|热门|精品|官方)(专题|专区)/.test(line)) continue
    const key = line.slice(0, 64)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(line)
    if (out.length >= limit) break
  }
  return out
}

export function formatFeedEvidenceNote(labels: string[]): string {
  const sample = labels.slice(0, 16).join(' | ')
  return `EVIDENCE: PAGE FEED（snapshot 可见；structured extract 可能为空）: ${sample}`
}
