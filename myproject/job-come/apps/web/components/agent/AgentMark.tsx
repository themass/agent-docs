/** JobCome agent avatar — circle with capital J. */

export function AgentMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  const fontSize = Math.round(size * 0.46);
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-slate-900 font-semibold text-white shadow-sm ${className}`}
      style={{ width: size, height: size, fontSize }}
      aria-hidden
    >
      J
    </span>
  );
}
