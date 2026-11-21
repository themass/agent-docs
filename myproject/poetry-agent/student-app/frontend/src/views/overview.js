/**
 * 时间轴 · 全貌. Quieter than 找诗: no cards, only the axis and its lines. Three layers: dynasties, how many
 * poets there are per 50 years, and theme lines. Only PUBLISHED items are drawn. Everything not organised is a
 * dashed band that says so; a missing bucket is "未收录", not "nobody wrote".
 */
import { el, activatable } from '../core/dom.js';
import { gaps, overlaps, spanText, yearText } from '../core/time.js';
import { header } from './timeline.js';

const FROM = -1000, TO = 1900, BUCKET = 50;

export function densityBuckets(people) {
  const out = [];
  for (let s = FROM; s < TO; s += BUCKET) {
    const e = s + BUCKET;
    out.push({ start: s, end: e, count: people.filter(p => p.startYear != null && p.timePrecision !== 'UNKNOWN' && overlaps({ start: p.startYear, end: p.endYear ?? p.startYear }, { start: s, end: e - 1 })).length });
  }
  return out;
}

export function themeSpan(theme) {
  const ys = theme.members.filter(m => m.startYear != null);
  return ys.length ? { start: Math.min(...ys.map(m => m.startYear)), end: Math.max(...ys.map(m => m.endYear ?? m.startYear)) } : null;
}

export async function overview(app) {
  const root = el('section', { class: 'page overview' }, header('看看全貌', 'overview'));
  let data;
  try { data = await app.repo.overview(); } catch {
    root.append(el('div', { class: 'card' }, el('p', { text: '全貌没有取到。' }), el('button', { class: 'btn', type: 'button', text: '重试', onclick: () => app.refresh() })));
    return root;
  }
  root.append(el('p', { class: 'coverage', text: data.coverageNotice }));
  const state = { px: 0.35, theme: null, year: null };
  const detail = el('div', { class: 'overview-detail', 'aria-live': 'polite' });
  const stage = el('div', { class: 'ov-scroll' });
  const zoom = el('div', { class: 'tl-controls' },
    ...[['−', 0.6], ['+', 1 / 0.6]].map(([t, f]) => el('button', { class: 'btn', type: 'button', text: t, 'aria-label': t === '+' ? '放大' : '缩小',
      onclick: () => { state.px = Math.min(3, Math.max(0.12, state.px * f)); draw(); } })));
  root.append(zoom, stage, detail);

  function draw() {
    const width = (TO - FROM) * state.px;
    const x = y => (y - FROM) * state.px;
    const canvas = el('div', { class: 'ov', style: `width:${width}px` });

    const dyn = el('div', { class: 'ov-row ov-dynasty', 'aria-label': '朝代' });
    const ranges = data.dynasties.filter(d => d.startYear != null).map(d => ({ start: d.startYear, end: d.endYear }));
    for (const g of gaps(FROM, TO, ranges)) dyn.append(el('div', { class: 'tl-gap', style: `left:${x(g.start)}px;width:${(g.end - g.start) * state.px}px`, text: g.end - g.start > 150 ? '还没有整理' : '' }));
    for (const d of data.dynasties) dyn.append(el('div', { class: 'tl-band', style: `left:${x(d.startYear)}px;width:${(d.endYear - d.startYear) * state.px}px` }, el('span', { class: 'tl-label', text: d.title })));

    const dens = el('div', { class: 'ov-row ov-density', 'aria-label': '诗人多少，每五十年' });
    for (const b of densityBuckets(data.people)) {
      dens.append(el('div', { class: `ov-cell${b.count ? '' : ' none'}`, style: `left:${x(b.start)}px;width:${BUCKET * state.px - 1}px;--n:${Math.min(b.count, 6)}`,
        title: b.count ? `${b.start}—${b.end} 年，收录 ${b.count} 位` : `${b.start}—${b.end} 年，未收录` }));
    }

    const themes = el('div', { class: 'ov-themes', 'aria-label': '主题线' });
    for (const t of data.themes) {
      const sp = themeSpan(t);
      if (!sp) continue;
      const row = el('div', { class: `ov-theme${state.theme === t.themeId ? ' selected' : ''}${state.theme && state.theme !== t.themeId ? ' dim' : ''}` },
        el('div', { class: 'ov-theme-dash', style: `left:0;width:${width}px` }),
        el('div', { class: 'ov-theme-line', style: `left:${x(sp.start)}px;width:${Math.max(4, (sp.end - sp.start) * state.px)}px` }),
        el('span', { class: 'tl-label', style: `left:${x(sp.start)}px`, text: t.title }));
      themes.append(activatable(row, () => { state.theme = state.theme === t.themeId ? null : t.themeId; state.year = null; draw(); }));
    }
    canvas.append(dyn, dens, themes, el('div', { class: 'tl-ruler' }, ...[-1000, -500, 0, 500, 1000, 1500].map(y => el('span', { style: `left:${x(y)}px`, text: yearText(y) }))));
    canvas.addEventListener('click', e => {
      if (e.target.closest('.ov-theme')) return;
      const r = canvas.getBoundingClientRect();
      state.year = Math.round(FROM + (e.clientX - r.left) / state.px);
      state.theme = null; draw();
    });
    stage.replaceChildren(canvas);

    detail.replaceChildren();
    if (state.theme) {
      const t = data.themes.find(v => v.themeId === state.theme);
      detail.append(el('h2', { text: t.title }), el('ol', { class: 'plain' }, ...[...t.members].sort((a, b) => a.startYear - b.startYear).map(m => el('li', { text: `${spanText(m)} · ${m.title}` }))));
    } else if (state.year != null) {
      const y = state.year;
      const hits = [...data.dynasties, ...data.people, ...data.works].filter(i => i.startYear != null && i.startYear <= y && (i.endYear ?? i.startYear) >= y);
      detail.append(el('h2', { text: `${yearText(y)}` }),
        hits.length ? el('ul', { class: 'plain' }, ...hits.map(i => el('li', { text: `${i.title} · ${spanText(i)}` })))
          : el('p', { class: 'soft', text: '这一年我们还没有收录。没收录不等于什么都没发生。' }));
    }
  }
  draw();
  return root;
}
