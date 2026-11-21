/**
 * 家长入口(占位). The gate here only stops a stray tap; it is not a security check. Real parental
 * verification is a native screen in the app shell (frontend-and-mobile-strategy.md section 8). Offers: what we
 * keep (and do not), and the two deletions. No reports, no payment, no account yet.
 */
import { el } from '../core/dom.js';
import { S } from '../strings.js';

export async function parent(app) {
  const a = 3 + Math.floor(Math.random() * 6), b = 4 + Math.floor(Math.random() * 5);
  const root = el('section', { class: 'page parent' }, el('h1', { text: '家长' }));
  const content = el('div', { hidden: true });
  const input = el('input', { type: 'number', inputmode: 'numeric', 'aria-label': `${a} 乘 ${b} 等于几` });
  const err = el('p', { class: 'soft', 'aria-live': 'polite' });
  const gate = el('div', { class: 'card' }, el('p', { text: '为了避免孩子误点，请先算一道题。' }),
    el('label', {}, `${a} × ${b} = `, input),
    el('button', { class: 'btn primary', type: 'button', text: '进入', onclick: () => {
      if (Number(input.value) === a * b) { gate.hidden = true; content.hidden = false; } else err.textContent = '再试一次。';
    } }), err);

  const status = el('p', { class: 'soft', 'aria-live': 'polite' });
  content.append(el('div', { class: 'card' }, el('h2', { text: S.consent.title }), el('p', { text: S.consent.body })),
    el('div', { class: 'card' }, el('h2', { text: '删除数据' }),
      el('p', { text: '“清除本机”会删掉这台设备上的进度、设置和缓存。“删除云端记录”会删掉服务器上与这台设备有关的全部学习记录，并重置匿名身份。' }),
      el('div', { class: 'asks' },
        el('button', { class: 'btn', type: 'button', text: '清除本机学习记录', onclick: () => {
          app.platform.kv.clearAll(); status.textContent = '已清除。刷新后生效。'; setTimeout(() => location.reload(), 600);
        } }),
        el('button', { class: 'btn', type: 'button', text: '删除云端记录', onclick: async () => {
          try { if (app.store.get('device')) await app.api.del('/devices/me', { auth: true }); app.store.set('device', null); status.textContent = '云端记录已删除，匿名身份已重置。'; }
          catch { status.textContent = '这会儿没连上，稍后再试。'; }
        } })), status),
    el('p', { class: 'soft', text: '家长报表、账号、付费：后面再做，现在没有。' }));
  root.append(gate, content);
  return root;
}
