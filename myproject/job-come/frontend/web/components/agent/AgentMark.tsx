/** 舟卡 avatar mark. */

export function AgentMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  const fontSize = Math.round(size * 0.42);
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full bg-brand-600 font-semibold text-white shadow-brand ${className}`}
      style={{ width: size, height: size, fontSize }}
      aria-hidden
    >
      舟
    </span>
  );
}
