import type { MetricValue } from '../types.js'

function formatUsd(n: number): string {
  return `$${n.toFixed(2)}`
}

function daysUntil(iso: string): number {
  const end = new Date(iso).getTime()
  if (!Number.isFinite(end)) return 0
  return Math.max(0, Math.ceil((end - Date.now()) / 86_400_000))
}

export function MetricValueView({ value }: { value: MetricValue }) {
  switch (value.kind) {
    case 'currency': {
      const limit = value.limitUsd != null ? formatUsd(value.limitUsd) : '—'
      const spent = formatUsd(value.spentUsd)
      const remaining =
        value.remainingUsd != null ? formatUsd(value.remainingUsd) : null
      const pct =
        value.percentUsed != null ? `${Math.min(100, value.percentUsed).toFixed(1)}%` : null
      const hasMoney = value.limitUsd != null || value.spentUsd > 0
      const headline = hasMoney ? spent : pct ?? spent
      return (
        <div className="gf-metric-currency">
          <strong>{headline}</strong>
          <small>
            {hasMoney && limit !== '—' ? ` / ${limit}` : ''}
            {remaining ? ` · 剩余 ${remaining}` : ''}
            {hasMoney && pct ? ` · ${pct}` : !hasMoney && pct ? ' 已用' : ''}
          </small>
          {value.percentUsed != null ? (
            <div className="gf-progress" aria-hidden>
              <span style={{ width: `${Math.min(100, value.percentUsed)}%` }} />
            </div>
          ) : null}
        </div>
      )
    }
    case 'countdown': {
      const days = daysUntil(value.cycleEnd)
      const start = new Date(value.cycleStart).toLocaleDateString()
      const end = new Date(value.cycleEnd).toLocaleDateString()
      return (
        <div>
          <strong>{days} 天</strong>
          <small>
            {start} → {end}
          </small>
        </div>
      )
    }
    case 'text':
      return (
        <div>
          <strong className={value.muted ? 'gf-muted' : undefined}>{value.text}</strong>
        </div>
      )
    case 'badge':
      return <span className={`gf-badge gf-badge-${value.tone ?? 'muted'}`}>{value.text}</span>
    case 'gauge':
      return (
        <div>
          <strong>
            {value.used}
            {value.limit != null ? ` / ${value.limit}` : ''}
            {value.unit ? ` ${value.unit}` : ''}
          </strong>
          {value.subtitle ? <small>{value.subtitle}</small> : null}
        </div>
      )
    case 'list':
      return (
        <ul className="gf-list">
          {value.items.map((item) => (
            <li key={`${item.label}-${item.value}`}>
              <span className="gf-list-label">{item.label}</span>
              <span className="gf-list-value">{item.value}</span>
              {item.hint ? <span className="gf-list-hint">{item.hint}</span> : null}
            </li>
          ))}
        </ul>
      )
    default:
      return null
  }
}
