export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString('zh-CN', { hour12: false });
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s === 0 ? `${m} 分` : `${m} 分 ${s} 秒`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString('zh-CN');
}

/** 0–100 的整数百分比;分母为 0 或缺失时返回 null。 */
export function percent(value: number | null | undefined, max: number | null | undefined): number | null {
  if (value === null || value === undefined || max === null || max === undefined || max <= 0) return null;
  return Math.round((value / max) * 100);
}

export function clampPercent(value: number | null): number {
  if (value === null) return 0;
  return Math.max(0, Math.min(100, value));
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}
