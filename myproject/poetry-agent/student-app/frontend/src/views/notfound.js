import { el } from '../core/dom.js';
export async function notfound() {
  return el('section', { class: 'page' }, el('h1', { text: '这里什么也没有' }), el('a', { class: 'btn primary', href: '#/', text: '回到我的时空' }));
}
