/**
 * Resolves a bundle asset id to something drawable, honouring the device budget and the declared
 * fallback chain (shared kernel `resolve`). The URL comes from the published registry (`uri`), never from
 * the bundle's own file hints. Whatever happens, the answer is either a thing to show or a reason it is text.
 */
import { ceiling, rank, resolve } from '../kernel/index.js';

export function budgetFrom({ mediaOff, weak, lowMemory, reducedMotion }) {
  return { forceLevel: mediaOff ? 'L0' : undefined, weakNetwork: !!weak, lowMemory: !!lowMemory, reducedMotion: !!reducedMotion };
}

export function modeOf(row) {
  if (!row) return 'text';
  if (row.kind === 'character') return 'character';
  const ext = String(row.uri || '').split('?')[0].split('.').pop().toLowerCase();
  if (ext === 'json' && row.kind === 'illustration') return 'parallax';
  if (['svg', 'webp', 'png', 'jpg', 'jpeg'].includes(ext)) return 'image';
  if (row.kind === 'audio' || ['m4a', 'mp3', 'ogg'].includes(ext)) return 'audio';
  return 'text';
}

export function createAssets({ assets, registry, budget, assetBase = '' }) {
  const urlOf = row => `${assetBase.replace(/\/$/, '')}/${String(row.uri).replace(/^\//, '')}`;
  return {
    ceiling: () => ceiling(budget()),
    /**
     * `override` narrows the budget for this one call, e.g. {forceLevel: 'L1'} to ask "what is the still-picture
     * version of this asset" after the animated one failed to load.
     */
    resolve(assetId, override = {}) {
      const spec = assets?.[assetId];
      if (!spec) return { assetId, mode: 'text', url: null, degraded: true, reason: 'missing', requested: assetId };
      const b = { ...budget(), ...override };
      let r;
      try { r = resolve(assetId, assets, b); } catch { return { assetId, mode: 'text', url: null, degraded: true, reason: 'broken-chain', requested: assetId }; }
      const row = registry?.get?.(r.assetId);
      if (!row) return { assetId: r.assetId, mode: 'text', url: null, degraded: true, reason: 'unregistered', requested: assetId };
      const cap = ceiling(b);
      const degraded = r.assetId !== assetId || rank(spec.level) > rank(cap);
      return { assetId: r.assetId, mode: modeOf(row), url: urlOf(row), uri: row.uri, level: r.level, degraded,
        reason: degraded ? (b.forceLevel ? 'user_off' : 'budget') : null, requested: assetId };
    },
    urlOf,
  };
}
