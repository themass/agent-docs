/**
 * Draws a character from a manifest published by the 2D-character task (production/contracts/character.schema.json).
 * Playback semantics live in character/core.js, a verbatim copy of the reference player. This file only
 * (1) validates and fetches, (2) hosts the requestAnimationFrame loop, (3) degrades.
 *
 * Failure ladder: svg-layers animation -> the manifest's still image -> a name seal. Any step failing
 * lands on the next one; the lines the character speaks are always on screen as text regardless.
 */
import { CharacterPlayer } from './core.js';
import { mountCharacter as mountSvg } from './dom.js';

const MAX_LAYER_BYTES = 200 * 1024;
const UNSAFE_SVG = /<\s*script|<\s*foreignObject|<\s*iframe|\son[a-z]+\s*=|javascript:|(?:xlink:)?href\s*=\s*["']\s*(?:https?:)?\/\//i;

export function validateManifest(m) {
  if (!m || typeof m !== 'object') return 'not an object';
  if (!/^1\.\d+$/.test(m.schema_version || '')) return 'schema_version';
  for (const k of ['character_id', 'display_name', 'canvas', 'anchors', 'default_state', 'states', 'degrade', 'depiction']) if (m[k] == null) return k;
  if (m.depiction.declared_as !== 'DRAMATIZATION') return 'depiction must be DRAMATIZATION';
  if (!m.states[m.default_state]) return 'default_state';
  return null;
}

export const isSafeSvg = text => typeof text === 'string' && text.length <= MAX_LAYER_BYTES && !UNSAFE_SVG.test(text);

export async function mountCharacter({ host, manifestUrl, reducedMotion = false, fetchImpl = globalThis.fetch?.bind(globalThis),
  win = globalThis, onFail = () => {} }) {
  const fail = why => { onFail(why); return null; };
  try {
    const res = await fetchImpl(manifestUrl, { credentials: 'omit' });
    if (!res.ok) return fail('manifest-http');
    const manifest = await res.json();
    const bad = validateManifest(manifest);
    if (bad) return fail(`manifest-invalid:${bad}`);
    const dir = manifestUrl.slice(0, manifestUrl.lastIndexOf('/') + 1);
    const notice = manifest.depiction.notice;

    if (manifest.renderer !== 'svg-layers') return await still(manifest, dir, host, fetchImpl, notice, fail);

    const texts = {};
    await Promise.all((manifest.layers || []).filter(l => l.file).map(async l => {
      const r = await fetchImpl(dir + l.file, { credentials: 'omit' });
      if (!r.ok) throw new Error('layer');
      const t = await r.text();
      if (!isSafeSvg(t)) throw new Error('unsafe');
      texts[l.id] = t;
    }));

    const player = new CharacterPlayer(manifest, { reducedMotion });
    const view = mountSvg(host, manifest, texts);
    let raf = 0, last = 0, alive = true, talkUntil = 0;
    const frame = t => {
      if (!alive) return;
      const dt = last ? Math.min(100, t - last) : 16;
      last = t;
      if (talkUntil && t > talkUntil) { talkUntil = 0; player.setState('idle'); }
      view.apply(player.tick(dt));
      if (!reducedMotion) raf = win.requestAnimationFrame(frame);
    };
    view.apply(player.tick(0));
    if (!reducedMotion) raf = win.requestAnimationFrame(frame);
    const onVis = () => { if (win.document?.hidden) { win.cancelAnimationFrame(raf); last = 0; } else if (alive && !reducedMotion) raf = win.requestAnimationFrame(frame); };
    win.document?.addEventListener('visibilitychange', onVis);

    return {
      name: manifest.display_name, notice, altText: manifest.degrade.text_alt, placeholder: !!manifest.placeholder?.is_placeholder,
      setState: s => { player.setState(s); if (reducedMotion) view.apply(player.tick(0)); },
      /** Mouth/head movement while a line is spoken; no sync to audio is promised (amplitude mode is optional). */
      talk(ms) { talkUntil = (win.performance?.now?.() ?? 0) + ms; player.setState('talk'); if (reducedMotion) view.apply(player.tick(0)); },
      destroy() { alive = false; win.cancelAnimationFrame(raf); win.document?.removeEventListener('visibilitychange', onVis); view.svg.remove(); },
    };
  } catch { return fail('load-failed'); }
}

async function still(manifest, dir, host, fetchImpl, notice, fail) {
  const file = manifest.degrade?.still?.file;
  if (!file) return fail('no-still');
  const img = host.ownerDocument.createElement('img');
  img.src = dir + file;
  img.alt = manifest.degrade.text_alt;
  img.style.cssText = 'width:100%;height:100%;object-fit:contain';
  host.append(img);
  return { name: manifest.display_name, notice, altText: manifest.degrade.text_alt, placeholder: !!manifest.placeholder?.is_placeholder,
    setState() {}, talk() {}, destroy() { img.remove(); } };
}
