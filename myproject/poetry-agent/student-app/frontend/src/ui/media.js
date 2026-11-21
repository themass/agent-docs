/**
 * Media containers. Every one of them can end as text with a plain explanation; none leaves a hole.
 * The author-facing `meaning` field of an asset is never shown to a learner.
 */
import { el } from '../core/dom.js';
import { S } from '../strings.js';

export function missingFrame(reason) {
  return el('div', { class: 'level-frame', dataset: { level: 'missing' }, role: 'note' },
    el('span', { text: reason === 'user_off' ? S.mediaOff : S.mediaFailed }));
}

export function renderMedia(resolved, { reducedMotion = false, onDegrade = () => {}, fetchImpl = globalThis.fetch?.bind(globalThis) } = {}) {
  if (!resolved || resolved.mode === 'text' || !resolved.url) {
    if (resolved?.degraded) onDegrade(resolved.reason || 'asset_failed');
    return resolved?.degraded ? missingFrame(resolved.reason) : null;
  }
  const frame = el('div', { class: 'level-frame', dataset: { level: resolved.level || 'L1' } });
  const fallback = why => { frame.replaceChildren(missingFrame(why)); frame.dataset.level = 'missing'; onDegrade('asset_failed'); };

  if (resolved.mode === 'image') {
    const img = el('img', { src: resolved.url, alt: '', loading: 'lazy', decoding: 'async' });
    img.addEventListener('error', () => fallback('asset_failed'));
    frame.append(img);
    if (resolved.degraded) onDegrade(resolved.reason);
  } else if (resolved.mode === 'parallax') {
    mountParallax(frame, resolved.url, { reducedMotion, fetchImpl }).catch(() => fallback('asset_failed'));
  } else {
    return null;
  }
  return frame;
}

/** Stacked layers that drift a hair with the pointer. Fully static under reduced motion. */
async function mountParallax(frame, url, { reducedMotion, fetchImpl }) {
  const res = await fetchImpl(url, { credentials: 'omit' });
  if (!res.ok) throw new Error('parallax');
  const spec = await res.json();
  const dir = url.slice(0, url.lastIndexOf('/') + 1);
  const stage = el('div', { class: 'parallax', style: `aspect-ratio:${spec.canvas.width}/${spec.canvas.height}` });
  const layers = (spec.layers || []).map(l => {
    const img = el('img', { src: dir + l.file, alt: '', loading: 'lazy', dataset: { depth: String(l.depth || 0) } });
    img.addEventListener('error', () => img.remove());
    stage.append(img);
    return img;
  });
  frame.append(stage);
  if (reducedMotion) return;
  const max = Number(spec.max_shift_pct || 2);
  frame.addEventListener('pointermove', e => {
    const r = frame.getBoundingClientRect();
    const dx = ((e.clientX - r.left) / r.width - 0.5) * 2;
    for (const img of layers) img.style.transform = `translateX(${(dx * Number(img.dataset.depth) * max).toFixed(2)}%)`;
  });
}
