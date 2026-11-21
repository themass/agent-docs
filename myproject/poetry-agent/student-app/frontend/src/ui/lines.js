/**
 * The poem, line by line. Text first, always: this renders from the poem pack and needs no media.
 * Used on the poem page, as the sticky side panel of a lesson, and as the line picker in 回.
 */
import { el, activatable } from '../core/dom.js';

export function renderLines({ lines, annotations = [], pinyin = false, onTap, showNotes = false }) {
  const hot = new Set();
  let selected = null;
  const root = el('ol', { class: 'poem', 'aria-label': '诗文' });
  const items = new Map();
  const visibleNotes = seq => annotations.filter(a => a.lineSeq === seq);

  for (const line of lines) {
    const noteBox = el('div', { class: 'notes', hidden: true });
    const li = el('li', { class: 'poem-line', dataset: { seq: String(line.seq) } },
      pinyin && line.pinyin ? el('span', { class: 'pinyin', text: line.pinyin }) : null,
      el('span', { class: 'line-text', text: line.text }), noteBox);
    activatable(li.querySelector('.line-text'), () => {
      selected = line.seq;
      refresh();
      if (showNotes) {
        const notes = visibleNotes(line.seq);
        noteBox.replaceChildren(...(notes.length ? notes.map(n => el('p', { class: 'note', text: n.text })) : [el('p', { class: 'note soft', text: '这一句的字词说明还在整理。' })]));
        noteBox.hidden = false;
      }
      onTap?.(line.seq);
    });
    root.append(li);
    items.set(line.seq, li);
  }
  function refresh() {
    for (const [seq, li] of items) {
      li.classList.toggle('hot', hot.has(seq));
      li.classList.toggle('selected', seq === selected);
      li.setAttribute('aria-current', String(seq === selected));
    }
  }
  return {
    el: root,
    /** Highlight lines a piece of background points at. Shape (rule + indent), not just colour. */
    setHot(seqs, { scroll = false } = {}) {
      hot.clear(); (seqs || []).forEach(s => hot.add(Number(s))); refresh();
      if (scroll && seqs?.length) items.get(Number(seqs[0]))?.scrollIntoView?.({ block: 'center', behavior: 'smooth' });
    },
    select(seq) { selected = seq; refresh(); },
    get selected() { return selected; },
  };
}
