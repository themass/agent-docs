/** Year wording. Pure, so it is unit-tested. Disputed or unknown dates are said out loud, never smoothed over. */
export const yearText = y => (y < 0 ? `公元前${-y}年` : `${y}年`);

export function spanText(item) {
  const { startYear: s, endYear: e, timePrecision: p } = item || {};
  if (p === 'UNKNOWN' || s == null) return '年代不可考';
  if (p === 'EXACT' || s === e) return yearText(s);
  const range = `${s < 0 ? `前${-s}` : s}—${e < 0 ? `前${-e}` : e}年`;
  return p === 'APPROXIMATE' ? `约 ${range}` : range;
}

/** Segments of [from,to] that none of the given [start,end] ranges cover: drawn as "not organised yet", not as empty. */
export function gaps(from, to, ranges) {
  const sorted = ranges.filter(r => r.end >= from && r.start <= to).map(r => ({ start: Math.max(r.start, from), end: Math.min(r.end, to) }))
    .sort((a, b) => a.start - b.start);
  const out = [];
  let cursor = from;
  for (const r of sorted) {
    if (r.start > cursor) out.push({ start: cursor, end: r.start });
    cursor = Math.max(cursor, r.end);
  }
  if (cursor < to) out.push({ start: cursor, end: to });
  return out;
}

/** Greedy lane packing so labels do not overlap. minWidth is in years. */
export function lanes(items, minWidth) {
  const ends = [];
  const placed = [...items].sort((a, b) => a.start - b.start).map(it => {
    const end = Math.max(it.end, it.start + minWidth);
    let lane = ends.findIndex(e => e <= it.start);
    if (lane < 0) { lane = ends.length; ends.push(end); } else ends[lane] = end;
    return { ...it, lane };
  });
  return { placed, count: Math.max(1, ends.length) };
}

export const overlaps = (a, b) => a.start <= b.end && b.start <= a.end;
