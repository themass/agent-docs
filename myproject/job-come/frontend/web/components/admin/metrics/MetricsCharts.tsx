"use client";

/**
 * Hand-rolled chart primitives for the admin monitoring panel.
 *
 * Deliberately not a charting library. What the panel needs is three things — a
 * ranked bar, a latency histogram, and a number tile — and the smallest library
 * that draws all three (Recharts) is ~100 KB for two SVG shapes. These stay
 * server-renderable, inherit the app's Tailwind palette without a theme object,
 * and draw nothing the operator cannot read at a glance.
 *
 * The rule callers rely on: **no data is not zero.** An empty series renders an
 * explicit message, never a zero-length bar — a flat zero line is what a broken
 * service looks like, and the two must not be confused.
 */

type BarDatum = {
  label: string;
  value: number;
  /** Shown at the end of the bar instead of the raw value, when a unit is needed. */
  display?: string;
  tone?: "brand" | "danger" | "muted";
};

const TONE_CLASS: Record<NonNullable<BarDatum["tone"]>, string> = {
  brand: "bg-brand-500",
  danger: "bg-danger-500",
  muted: "bg-ink-300",
};

/**
 * A ranked horizontal bar list — the honest shape for "which scenario is slow".
 *
 * Horizontal because the labels are words ("coach", "resume-writer"), and a
 * vertical chart would either rotate them or overlap them.
 */
export function BarList({
  data,
  emptyLabel = "暂无数据",
  max,
}: {
  data: BarDatum[];
  emptyLabel?: string;
  /** Force the axis maximum so several panels stay comparable. */
  max?: number;
}) {
  if (data.length === 0) {
    return <p className="py-6 text-center text-xs text-ink-500">{emptyLabel}</p>;
  }
  const ceiling = max ?? Math.max(...data.map((d) => d.value), Number.EPSILON);
  return (
    <ul className="space-y-1.5">
      {data.map((d) => {
        const pct = ceiling > 0 ? Math.max((d.value / ceiling) * 100, d.value > 0 ? 1.5 : 0) : 0;
        return (
          <li key={d.label} className="text-xs">
            <div className="flex items-baseline justify-between gap-2">
              <span className="min-w-0 truncate text-ink-700" title={d.label}>
                {d.label}
              </span>
              <span className="shrink-0 font-medium tabular-nums text-ink-900">
                {d.display ?? d.value.toLocaleString("zh-CN")}
              </span>
            </div>
            <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-ink-100">
              <div
                className={`h-full rounded-full ${TONE_CLASS[d.tone ?? "brand"]}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

type HistogramBucket = { upper: number; count: number };

/**
 * A latency histogram as horizontal bands.
 *
 * Cumulative Prometheus buckets are converted to per-band counts here, because
 * "how many calls took 3–5 s" is the question a person asks; "how many took less
 * than 5 s" is not. The conversion cannot invent data: a band is the difference
 * between two cumulative counts, so a missing bucket degrades to a wider band.
 */
export function HistogramBars({
  buckets,
  emptyLabel = "暂无数据",
}: {
  buckets: HistogramBucket[];
  emptyLabel?: string;
}) {
  const bands = toBands(buckets);
  const total = bands.reduce((sum, b) => sum + b.count, 0);
  if (total === 0) {
    return <p className="py-6 text-center text-xs text-ink-500">{emptyLabel}</p>;
  }
  const peak = Math.max(...bands.map((b) => b.count), 1);
  return (
    <ul className="space-y-1">
      {bands.map((band) => (
        <li key={band.label} className="flex items-center gap-2 text-xs">
          <span className="w-16 shrink-0 text-right tabular-nums text-ink-500">{band.label}</span>
          <span className="h-3 flex-1 overflow-hidden rounded-sm bg-ink-100">
            <span
              className="block h-full rounded-sm bg-brand-400"
              style={{ width: `${(band.count / peak) * 100}%` }}
            />
          </span>
          <span className="w-12 shrink-0 tabular-nums text-ink-700">{band.count}</span>
        </li>
      ))}
    </ul>
  );
}

function toBands(buckets: HistogramBucket[]): Array<{ label: string; count: number }> {
  const sorted = [...buckets].sort((a, b) => a.upper - b.upper);
  const bands: Array<{ label: string; count: number }> = [];
  let previous = 0;
  let previousUpper = 0;
  for (const bucket of sorted) {
    const count = Math.max(bucket.count - previous, 0);
    if (count > 0) {
      const label =
        Number.isFinite(bucket.upper) && bucket.upper > previousUpper
          ? `${formatCompact(previousUpper)}–${formatCompact(bucket.upper)}`
          : `≥${formatCompact(previousUpper)}`;
      bands.push({ label, count });
    }
    previous = bucket.count;
    previousUpper = bucket.upper;
  }
  return bands;
}

export function formatCompact(seconds: number): string {
  if (!Number.isFinite(seconds)) return "∞";
  if (seconds >= 1) return `${Number(seconds.toFixed(seconds >= 10 ? 0 : 1))}s`;
  return `${Math.round(seconds * 1000)}ms`;
}

/** A single number with its caption — the summary row at the top of the panel. */
export function StatTile({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "danger" | "warn";
}) {
  const valueClass =
    tone === "danger" ? "text-danger-600" : tone === "warn" ? "text-warn-600" : "text-ink-900";
  return (
    <div className="rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-card">
      <p className="text-micro text-ink-500">{label}</p>
      <p className={`text-lg font-semibold tabular-nums ${valueClass}`}>{value}</p>
      {hint ? <p className="text-micro text-ink-500">{hint}</p> : null}
    </div>
  );
}
