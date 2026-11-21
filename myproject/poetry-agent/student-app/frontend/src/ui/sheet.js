/** A modal sheet: Escape closes, focus returns to the opener, tapping the backdrop closes. */
import { el } from '../core/dom.js';

export function sheet(app, { title, body }) {
  const opener = document.activeElement;
  const root = document.getElementById('sheet-root') || document.body;
  const close = () => { node.remove(); document.removeEventListener('keydown', onKey); opener?.focus?.(); };
  const onKey = e => { if (e.key === 'Escape') close(); };
  const node = el('div', { class: 'sheet-backdrop', onclick: e => { if (e.target === node) close(); } },
    el('div', { class: 'sheet', role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      el('div', { class: 'sheet-head' }, el('strong', { text: title }), el('button', { class: 'btn', type: 'button', 'aria-label': '关闭', text: '×', onclick: close })), body));
  document.addEventListener('keydown', onKey);
  root.append(node);
  node.querySelector('button')?.focus();
  return close;
}
