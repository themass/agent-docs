/**
 * The trust contract from docs/design/DESIGN.md section 4, as code: fact = indigo underline (tap for
 * the source), interpretation = green left rule, dramatization = vermilion "演绎" tag, unexamined = grey dashes.
 * A dramatization without its badge text is NOT rendered at all (returns null): a spoken line that
 * could be mistaken for history is worse than a missing line.
 */
import { el, activatable } from '../core/dom.js';

export const KIND_LABEL = { FACT: '史实', INTERPRETATION: '理解', DRAMATIZATION: '演绎', UNKNOWN: '不可考' };

/**
 * OQ-01（2026-11-11 定）：演绎只有一句固定的话，三处（文字卡、bundle、界面）都用它，一个字都不许改。
 * 改这句话就是改产品铁律，所以它只在这里出现一次。
 */
export const DRAMATIZATION_NOTICE = '这是教学演绎，不是史料。';
/** 角标用的短形式：场景常驻角标 + 诗人说话时再加一个。 */
export const DRAMATIZATION_TAG = '演绎 · 不是史料';
const KIND_CLASS = { FACT: 'basis--fact', INTERPRETATION: 'basis--interp', DRAMATIZATION: 'basis--drama', UNKNOWN: 'basis--unknown' };

/**
 * The one place a trust tag is made. A dramatization always reads DRAMATIZATION_TAG verbatim: the wording is
 * fixed (OQ-01), the compiler checks that the bundle carries the same words, and it is real text (no CSS
 * ::before), so screen readers say it and nothing upstream can double or reword it.
 */
export function kindBadge(kind) {
  const k = KIND_CLASS[kind] ? kind : 'UNKNOWN';
  return el('span', { class: `basis ${KIND_CLASS[k]}`, text: k === 'DRAMATIZATION' ? DRAMATIZATION_TAG : KIND_LABEL[k] });
}

export function spoken(line, { onBasis, who } = {}) {
  const kind = line.kind;
  if (kind === 'DRAMATIZATION' && !line.badge) return null;
  const cls = { FACT: 'basis--fact', INTERPRETATION: 'basis--interp', DRAMATIZATION: 'basis--drama', UNKNOWN: 'basis--unknown' }[kind] || 'basis--unknown';
  const text = el('span', { class: 'spoken-text', text: line.text });
  const children = [kindBadge(kind)];
  const row = el('p', { class: `spoken ${cls}`, dataset: { kind, id: line.id || '' } }, who ? el('strong', { class: 'who', text: `${who}：` }) : null, text, ...children);
  if (kind === 'FACT' && onBasis) {
    const link = activatable(el('span', { class: 'source-link', text: '出处' }), () => onBasis(line));
    row.append(' ', link);
  }
  return row;
}

export function trustLegend() {
  return el('p', { class: 'legend', 'aria-label': '标记说明' },
    kindBadge('FACT'), ' 有出处　', kindBadge('INTERPRETATION'), ' 是解释，不是史料　',
    kindBadge('DRAMATIZATION'), ' 想象的场面　', kindBadge('UNKNOWN'), ' 没有定论');
}
