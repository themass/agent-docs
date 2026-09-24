export type Point = { x: number; y: number }

/** Catmull-Rom spline through pointer samples for replay trail. */
export function smoothPath(points: Point[], segmentsPerSpan = 8): Point[] {
  if (points.length < 2) return [...points]
  const out: Point[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(0, i - 1)]!
    const p1 = points[i]!
    const p2 = points[i + 1]!
    const p3 = points[Math.min(points.length - 1, i + 2)]!
    for (let s = 0; s < segmentsPerSpan; s++) {
      const t = s / segmentsPerSpan
      const t2 = t * t
      const t3 = t2 * t
      out.push({
        x:
          0.5 *
          (2 * p1.x +
            (-p0.x + p2.x) * t +
            (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 +
            (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
        y:
          0.5 *
          (2 * p1.y +
            (-p0.y + p2.y) * t +
            (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 +
            (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3),
      })
    }
  }
  out.push(points[points.length - 1]!)
  return out
}

/** Map replay clock (ms) → position along smoothed path. */
export function positionAtTime(
  pointerTimes: number[],
  path: Point[],
  elapsedMs: number
): Point | null {
  if (!pointerTimes.length || !path.length) return null
  if (elapsedMs <= pointerTimes[0]!) return path[0]!
  const last = pointerTimes.length - 1
  if (elapsedMs >= pointerTimes[last]!) return path[path.length - 1]!

  let i = 0
  while (i < last && pointerTimes[i + 1]! < elapsedMs) i++
  const t0 = pointerTimes[i]!
  const t1 = pointerTimes[i + 1]!
  const ratio = t1 > t0 ? (elapsedMs - t0) / (t1 - t0) : 0
  const pathIndex = Math.min(path.length - 1, Math.round((i + ratio) * (path.length / pointerTimes.length)))
  return path[pathIndex] ?? path[path.length - 1]!
}
