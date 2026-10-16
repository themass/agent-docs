"use client";

/** Shared so callers render the same dimension names as the chart. */
export const DIMENSION_LABELS: Record<string, string> = {
  structure: "结构",
  relevance: "相关",
  depth: "深度",
  communication: "表达",
  reflection: "复盘",
};

type Props = {
  scores: Record<string, number>;
  size?: number;
};

export function DimensionRadar({ scores, size = 200 }: Props) {
  const keys = Object.keys(DIMENSION_LABELS).filter((k) => typeof scores[k] === "number");
  if (keys.length < 3) {
    return (
      <p className="text-xs text-ink-500">暂无五维评分数据</p>
    );
  }

  const cx = size / 2;
  const cy = size / 2;
  const maxR = size * 0.36;
  const n = keys.length;

  const point = (i: number, value: number) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const r = (value / 10) * maxR;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  };

  const gridLevels = [2, 4, 6, 8, 10];
  const dataPoints = keys
    .map((k, i) => point(i, scores[k] ?? 0))
    .map(([x, y]) => `${x},${y}`)
    .join(" ");

  return (
    <svg width={size} height={size} className="text-ink-600">
      {gridLevels.map((level) => {
        const pts = keys
          .map((_, i) => point(i, level))
          .map(([x, y]) => `${x},${y}`)
          .join(" ");
        return (
          <polygon
            key={level}
            points={pts}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.12}
          />
        );
      })}
      {keys.map((k, i) => {
        const [x, y] = point(i, 10);
        const [lx, ly] = point(i, 11.5);
        return (
          <g key={k}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="currentColor" strokeOpacity={0.15} />
            <text
              x={lx}
              y={ly}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-ink-500 text-micro"
            >
              {DIMENSION_LABELS[k] ?? k}
            </text>
          </g>
        );
      })}
      <polygon
        points={dataPoints}
        className="fill-brand-500/20 stroke-brand-600"
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
    </svg>
  );
}
