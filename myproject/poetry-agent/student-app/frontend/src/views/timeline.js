/**
 * 时间轴 · 找诗. Zoom changes what is drawn, not just its size: dynasties/periods when zoomed out, events
 * next, then lifelines and works. Years nobody has organised are drawn as dashed "还没有整理" bands, never as
 * empty space, and the coverage sentence comes from the API. Selecting dims what is not from the same time.
 */
import { el, activatable } from '../core/dom.js';
import { gaps, lanes, overlaps, spanText } from '../core/time.js';

export const LEVELS = [
  { span: 1500, name: '朝代', types: ['DYNASTY'] },
  { span: 300, name: '分期', types: ['DYNASTY', 'PERIOD', 'EVENT'] },
  { span: 60, name: '事件', types: ['PERIOD', 'EVENT', 'EXPERIENCE', 'PERSON'] },
  { span: 24, name: '诗人与作品', types: ['EVENT', 'EXPERIENCE', 'PERSON', 'WORK'] },
];
const MAX_QUERY_SPAN = 4000;

export async function timeline(app) {
  const { repo } = app;
  const root = el('section', { class: 'page timeline' }, header('找一首诗', 'find'));
  const body = el('div', { class: 'tl-body' });
  root.append(body);

  let data;
  try { data = await repo.timeline(-1000, 1000, 100); } catch { return fail(root, app); }
  const items = data.results.items;
  const lessons = new Set(data.lessonWorkIds || []);
  const firstLesson = items.find(i => i.entityType === 'WORK' && lessons.has(i.id));
  const state = { center: firstLesson?.startYear ?? 750, level: firstLesson ? 3 : 1, selected: null };

  root.append(el('p', { class: 'coverage', text: data.coverageNotice }));
  const summary = el('div', { class: 'summary card', 'aria-live': 'polite' });
  root.append(summary);

  async function draw() {
    const lv = LEVELS[state.level];
    const half = lv.span / 2;
    const from = Math.round(state.center - half), to = Math.round(state.center + half);
    let view = items;
    if (to - from <= MAX_QUERY_SPAN) {
      try { view = (await repo.timeline(Math.max(-9999, from - lv.span), Math.min(9999, to + lv.span), 100)).results.items; } catch { /* keep what we have */ }
    }
    body.replaceChildren(app.platform.env.isNarrow() ? list(view, lv, state, lessons, onSelect) : axis(view, lv, from, to, state, lessons, onSelect));
    body.prepend(controls(state, draw));
    showSummary();
    function onSelect(it) { state.selected = it; draw(); }
    function showSummary() {
      summary.replaceChildren();
      const it = state.selected;
      if (!it) { summary.hidden = true; return; }
      summary.hidden = false;
      summary.append(el('h2', { text: it.title }), el('p', { class: 'soft', text: spanText(it) }), it.summary ? el('p', { text: it.summary }) : null);
      if (it.entityType === 'WORK') {
        summary.append(lessons.has(it.id) ? el('a', { class: 'btn primary', href: `#/poem/${it.id}`, text: '读这首诗' })
          : el('p', { class: 'soft', text: '场景整理中，原文先放这里。' }));
      }
    }
  }
  draw();
  const keys = e => {
    if (e.key === 'ArrowLeft') { state.center -= LEVELS[state.level].span / 4; draw(); }
    else if (e.key === 'ArrowRight') { state.center += LEVELS[state.level].span / 4; draw(); }
    else if (e.key === '+' || e.key === '=') { state.level = Math.min(LEVELS.length - 1, state.level + 1); draw(); }
    else if (e.key === '-') { state.level = Math.max(0, state.level - 1); draw(); }
    else if (e.key === 'Escape') { state.selected = null; draw(); }
  };
  root.tabIndex = 0;
  root.addEventListener('keydown', keys);
  return root;
}

export function header(title, mode) {
  return el('div', { class: 'tl-head' }, el('h1', { text: title }),
    el('div', { class: 'tabs', role: 'tablist' },
      el('a', { href: '#/timeline', role: 'tab', 'aria-selected': String(mode === 'find'), text: '找诗' }),
      el('a', { href: '#/timeline/overview', role: 'tab', 'aria-selected': String(mode === 'overview'), text: '看全貌' })));
}

function controls(state, draw) {
  const go = fn => () => { fn(); draw(); };
  const lv = LEVELS[state.level];
  return el('div', { class: 'tl-controls' },
    el('button', { class: 'btn', type: 'button', 'aria-label': '往前', text: '‹', onclick: go(() => { state.center -= lv.span / 3; }) }),
    el('span', { class: 'tl-level', text: `${lv.name} · ${Math.round(state.center - lv.span / 2)}—${Math.round(state.center + lv.span / 2)}` }),
    el('button', { class: 'btn', type: 'button', 'aria-label': '往后', text: '›', onclick: go(() => { state.center += lv.span / 3; }) }),
    el('button', { class: 'btn', type: 'button', 'aria-label': '缩小', text: '−', disabled: state.level === 0, onclick: go(() => { state.level -= 1; }) }),
    el('button', { class: 'btn', type: 'button', 'aria-label': '放大', text: '+', disabled: state.level === LEVELS.length - 1, onclick: go(() => { state.level += 1; }) }));
}

function visible(items, lv) { return items.filter(i => lv.types.includes(i.entityType) && i.timePrecision !== 'UNKNOWN' && i.startYear != null); }

function axis(items, lv, from, to, state, lessons, onSelect) {
  const span = to - from;
  const pct = y => ((Math.min(Math.max(y, from), to) - from) / span) * 100;
  const wrap = el('div', { class: 'tl-axis', role: 'group', 'aria-label': '时间轴' });
  const shown = visible(items, lv);
  const bands = shown.filter(i => i.entityType === 'DYNASTY' || i.entityType === 'PERIOD');

  const bandRow = el('div', { class: 'tl-row tl-bands' });
  for (const g of gaps(from, to, bands.map(b => ({ start: b.startYear, end: b.endYear })))) {
    bandRow.append(el('div', { class: 'tl-gap', style: `left:${pct(g.start)}%;width:${pct(g.end) - pct(g.start)}%`, text: '这一段还没有整理' }));
  }
  for (const b of bands) bandRow.append(mark('tl-band', b, `left:${pct(b.startYear)}%;width:${Math.max(0.5, pct(b.endYear) - pct(b.startYear))}%`, state, onSelect));
  wrap.append(bandRow);

  const rest = shown.filter(i => !bands.includes(i));
  const { placed, count } = lanes(rest.map(i => ({ it: i, start: i.startYear, end: i.endYear ?? i.startYear })), span * 0.14);
  const rows = el('div', { class: 'tl-lanes', style: `height:${count * 3.1}rem` });
  for (const p of placed) {
    const it = p.it;
    const point = it.entityType === 'WORK';
    const cls = point ? (lessons.has(it.id) ? 'tl-point tl-square' : 'tl-point tl-dot') : 'tl-bar';
    const left = pct(it.startYear), width = point ? 0 : Math.max(0.8, pct(it.endYear ?? it.startYear) - left);
    rows.append(mark(cls, it, `left:${left}%;top:${p.lane * 3.1}rem;${width ? `width:${width}%` : ''}`, state, onSelect));
  }
  wrap.append(rows);
  wrap.append(el('div', { class: 'tl-ruler' }, ...[0, 0.25, 0.5, 0.75, 1].map(f => el('span', { style: `left:${f * 100}%`, text: String(Math.round(from + f * span)) }))));
  return wrap;
}

function mark(cls, it, style, state, onSelect) {
  const sel = state.selected;
  const dim = sel && !(sel.id === it.id || overlaps({ start: sel.startYear, end: sel.endYear ?? sel.startYear }, { start: it.startYear, end: it.endYear ?? it.startYear }));
  const node = el('div', { class: `${cls}${sel?.id === it.id ? ' selected' : ''}${dim ? ' dim' : ''}`, style, 'aria-label': `${it.title}，${spanText(it)}`, dataset: { id: it.id, type: it.entityType } },
    el('span', { class: 'tl-label', text: it.title }));
  return activatable(node, () => onSelect(it));
}

function list(items, lv, state, lessons, onSelect) {
  const wrap = el('ul', { class: 'tl-list' });
  const shown = visible(items, lv).sort((a, b) => a.startYear - b.startYear);
  if (!shown.length) wrap.append(el('li', { class: 'tl-gap', text: '这一段还没有整理' }));
  for (const it of shown) {
    wrap.append(el('li', {}, activatable(el('div', { class: `card tl-item${state.selected?.id === it.id ? ' selected' : ''}`, 'aria-label': `${it.title}，${spanText(it)}` },
      el('strong', { text: it.title }), el('span', { class: 'soft', text: ` ${spanText(it)}` }),
      it.entityType === 'WORK' && lessons.has(it.id) ? el('span', { class: 'chip', text: '可进入' }) : null), () => onSelect(it))));
  }
  return wrap;
}

function fail(root, app) {
  root.append(el('div', { class: 'card' }, el('p', { text: '时间轴没有取到。' }),
    el('button', { class: 'btn', type: 'button', text: '重试', onclick: () => app.refresh() })));
  return root;
}
