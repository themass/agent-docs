/**
 * 诗词页. Order is the order of understanding and must not be rearranged: the poem, then the words, then
 * (only after) why it was written. Background rows are structured (layer, text, which lines they answer),
 * so tapping either side lights the other. Nothing here is written by the app: text is the poem pack.
 */
import { el } from '../core/dom.js';
import { renderLines } from '../ui/lines.js';
import { kindBadge } from '../ui/trust.js';
import { S } from '../strings.js';
import { sheet } from '../ui/sheet.js';

const LAYER_ORDER = ['WORLD', 'CITY', 'PERSON', 'SCENE'];

/**
 * One background per layer, in reading order. The reader is not split by grade (2026-11-12): the server
 * already sends one text per layer. Offline/fixture packs can still carry per-grade variants written before
 * that decision, so the same preference applies here: no-grade text first, then the fuller (non-PRIMARY) one.
 */
const RANK = b => (!b.audience ? 0 : b.audience === 'PRIMARY' ? 2 : 1);
export function pickBackgrounds(backgrounds) {
  const out = [];
  for (const layer of LAYER_ORDER) {
    const of = backgrounds.filter(b => b.layer === layer).sort((x, y) => RANK(x) - RANK(y));
    if (of[0]) out.push(of[0]);
  }
  return out;
}

export async function poem(app, { workId }) {
  const { repo, store } = app;
  let pack, lesson = null;
  try { [pack, lesson] = await Promise.all([repo.pack(workId), repo.lesson(workId)]); }
  catch (e) {
    return el('section', { class: 'page' }, el('h1', { text: '这首诗还没准备好' }),
      el('p', { class: 'soft', text: e?.status === 404 ? '还在整理，原文和注释先不放出来。' : '没有取到，稍后再试。' }),
      el('a', { class: 'btn', href: '#/timeline', text: '去时间轴' }));
  }
  const root = el('section', { class: 'page poem-page' });
  const author = pack.authors?.[0]?.name;
  root.append(el('a', { class: 'back', href: '#/timeline', text: '‹ 时间轴' }), el('h1', { text: pack.title }),
    el('p', { class: 'byline', text: [author, writtenAt(pack)].filter(Boolean).join(' · ') }));

  const hasPinyin = pack.lines.some(l => l.pinyin);
  const tools = el('div', { class: 'tools' },
    el('label', { class: 'switch' }, el('input', { type: 'checkbox', checked: store.pinyinOn() && hasPinyin, disabled: !hasPinyin, onchange: e => { store.set('pinyin', e.target.checked); app.refresh(); } }),
      el('span', { text: hasPinyin ? '拼音' : '暂无拼音' })));
  const lines = renderLines({ lines: pack.lines, annotations: pack.annotations, pinyin: store.pinyinOn(), showNotes: true,
    onTap: seq => highlight([seq]) });
  root.append(tools, lines.el);

  root.append(enterBlock(app, workId, lesson));

  if (pack.annotations.length) {
    root.append(el('h2', { text: '注释' }), el('ul', { class: 'plain' },
      ...pack.annotations.map(a => el('li', { text: a.text }))));
  }

  const rows = new Map();
  const bgs = pickBackgrounds(pack.backgrounds);
  if (bgs.length) {
    const table = el('div', { class: 'context', id: 'context' }, el('h2', { text: '他为什么写下这首诗' }));
    for (const b of bgs) {
      const seqs = pack.relations.filter(r => r.backgroundId === b.id).map(r => r.lineSeq).sort((x, y) => x - y);
      const row = el('div', { class: 'context-row', dataset: { layer: b.layer } },
        el('strong', { text: S.layers[b.layer] }), el('p', { text: b.body }),
        b.claimKind ? kindBadge(b.claimKind) : null,
        seqs.length ? el('button', { class: 'linkline', type: 'button', text: `↳ 对应第 ${seqs.join('、')} 句`, onclick: () => highlight(seqs, true) })
          : el('p', { class: 'soft', text: '这条背景暂时没绑定诗句。' }));
      rows.set(b.id, { row, seqs });
      table.append(row);
    }
    root.append(table);
  } else {
    root.append(el('div', { class: 'card' }, el('p', { text: '这首诗的背景我们还在整理。' })));
  }
  function highlight(seqs, scroll) {
    lines.setHot(seqs, { scroll });
    for (const { row, seqs: s } of rows.values()) row.classList.toggle('active', s.some(x => seqs.includes(x)));
  }

  root.append(sources(app, pack));
  root.append(el('p', { class: 'coverage', text: pack.coverageNotice }));
  if (pack.warnings?.length && store.get('source') === 'demo-fixture') root.append(el('p', { class: 'soft', text: pack.warnings.join('；') }));
  return root;
}

function writtenAt(pack) {
  const picked = (pack.writtenAt || []).find(c => c.selected) || pack.writtenAt?.[0];
  if (!picked) return '写作年代不可考';
  const others = (pack.writtenAt || []).filter(c => c !== picked);
  return others.length ? `${[picked, ...others].map(c => c.text).join(' 或 ')}（两说并存）` : picked.text;
}

function enterBlock(app, workId, lesson) {
  if (!lesson) return el('div', { class: 'enter' }, el('button', { class: 'btn big', type: 'button', disabled: true, text: '场景整理中' }), el('p', { class: 'soft', text: '原文和注释照常能读。' }));
  const p = app.store.progressOf(workId);
  return el('div', { class: 'enter' },
    el('a', { class: 'btn big primary', href: `#/lesson/${workId}/${p?.lastStep || 'read'}`, text: p ? '接着走' : '进入那一年' }),
    p ? el('a', { class: 'btn', href: `#/lesson/${workId}/read`, text: '从头读' }) : null);
}

function sources(app, pack) {
  const box = el('details', { class: 'sources' }, el('summary', { text: '出处与说法' }));
  const list = el('ul', { class: 'plain' });
  for (const c of pack.writtenAt || []) {
    list.append(el('li', {}, `${c.text}${c.selected ? '（采用）' : '（另有说法）'}`, ' ',
      el('button', { class: 'linkline', type: 'button', text: '看出处', onclick: () => showCitations(app, c.claimId) })));
  }
  if (!list.children.length) list.append(el('li', { class: 'soft', text: '写作年代没有收录。' }));
  box.append(list);
  return box;
}

export async function showCitations(app, claimId) {
  const body = el('div', {}, el('p', { class: 'soft', text: '正在取出处…' }));
  const close = sheet(app, { title: '出处', body });
  try {
    const rows = await app.repo.citations(claimId);
    body.replaceChildren(rows.length ? el('ul', { class: 'plain' }, ...rows.map(r => el('li', {}, el('strong', { text: r.title || '' }), ` ${[r.author, r.edition].filter(Boolean).join(' ')}`, r.locator ? el('div', { class: 'soft', text: `位置：${r.locator}` }) : null)))
      : el('p', { text: '这条的出处还没有核对完，所以暂时不能当作定论。' }));
  } catch { body.replaceChildren(el('p', { text: '出处这会儿没取到。' })); }
  return close;
}
