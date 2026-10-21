import type { ReactNode } from "react";

/**
 * Metric tile. `tone` only changes the value colour, never the surface, so a
 * row of tiles stays a calm row rather than a traffic light.
 */
export function StatTile({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "neutral" | "brand" | "success" | "warn";
}) {
  const valueTone = {
    neutral: "text-ink-900",
    brand: "text-brand-700",
    success: "text-success-700",
    warn: "text-warn-700",
  }[tone];
  return (
    <div className="card p-4">
      <p className="label-meta">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tabular-nums ${valueTone}`}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-ink-500">{hint}</p> : null}
    </div>
  );
}
