/**
 * Which audio asset narrates which spoken line.
 *
 * The bundle's lines carry no audio reference (contract proposal in docs/handoff/B.md). Until they do, the
 * mapping is read from the asset registry's sidecar `usage` table (production/published/bundles/<poem>.assets.json),
 * whose keys are bundle paths such as `steps[1].layers[0].lines[0]`. `indexBundle` records the same path on every fact,
 * so the two meet without either side inventing an id. A line that names its own `audio` wins over the sidecar.
 *
 * Everything here is optional. No sidecar, no entry for a line, or an asset that cannot play: the line is still
 * on screen as text, which is the caption, and nothing is announced as an error.
 */
const LINE_PATH = /^steps\[\d+\]\.(?:layers|roleplay\.layers)\[\d+\]\.lines\[\d+\]$/;

/** Pure: usage table + indexed bundle -> Map(factId -> audio asset id). Only assets the bundle itself declares as audio. */
export function mapNarration(usage, index, bundleAssets) {
  const byPath = new Map([...index.facts.values()].map(f => [f.path, f]));
  const out = new Map();
  for (const f of index.facts.values()) if (f.audio && bundleAssets?.[f.audio]) out.set(f.id, f.audio);
  for (const [assetId, paths] of Object.entries(usage || {})) {
    if (bundleAssets?.[assetId]?.kind !== 'audio') continue;
    for (const p of paths || []) {
      if (!LINE_PATH.test(p)) continue;                  // `cast[0].voice_id`, `assets.x.fallback`, `steps[4].demo_audio`: not a spoken line
      const fact = byPath.get(p);
      if (fact && !out.has(fact.id)) out.set(fact.id, assetId);
    }
  }
  return out;
}

/** Fetches the sidecar for a work (`work-chun-wang` -> `bundles/chun-wang.assets.json`); null when absent. */
export async function loadUsage({ assetBase, workId, fetchImpl = globalThis.fetch?.bind(globalThis) }) {
  const slug = String(workId).replace(/^work-/, '');
  if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(slug)) return null;
  try {
    const res = await fetchImpl(`${assetBase.replace(/\/$/, '')}/bundles/${slug}.assets.json`, { credentials: 'omit' });
    if (!res.ok) return null;
    const body = await res.json();
    return body && typeof body.usage === 'object' ? body.usage : null;
  } catch { return null; }
}

export async function loadNarration({ assetBase, workId, index, bundleAssets, fetchImpl }) {
  return mapNarration(await loadUsage({ assetBase, workId, fetchImpl }), index, bundleAssets);
}
