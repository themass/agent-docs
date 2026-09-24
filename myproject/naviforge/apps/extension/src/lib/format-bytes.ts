/** Human-readable byte size (e.g. `1.2 MB`, `840 KB`). */
export function formatBytes(bytes: number | undefined | null): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB'] as const
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = unit === 0 ? 0 : value < 10 ? 1 : 0
  const num = value.toFixed(digits).replace(/\.0$/, '')
  return `${num} ${units[unit]}`
}
