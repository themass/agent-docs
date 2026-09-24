export function formatRunElapsed(ms: number): string {
  const safe = Math.max(0, Math.round(ms))
  if (safe < 1000) return `${safe} ms`
  return `${(safe / 1000).toFixed(1)} s`
}

export function formatRunSubtitle(result: { target?: string; elapsedMs: number }): string {
  return [result.target, formatRunElapsed(result.elapsedMs)].filter(Boolean).join(' · ')
}
