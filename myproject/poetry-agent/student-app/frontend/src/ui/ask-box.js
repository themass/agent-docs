/**
 * 「我想问」：读者用自己的话问一个问题。
 *
 * 为什么有这个组件：此前读者只能点预设的几个动作，问不出「他为什么哭」。理解要从读者自己的问题开始。
 * 后端早就支持（agent 的 free_text：先过安全筛查，再路由到已有的、有出处的回答；路由不到就诚实说答不了），
 * 缺的只是前端这一个入口。
 *
 * 边界（都不是这个组件决定的，但它必须守住）
 *  - 打的字只发给 agent 的 /turn，不进事件、不进本地存储、不回显：发出去就清空输入框。
 *  - 不记成事件：问过什么、问没问，都不进事件队列（lesson.js 对 free_text 不调 session.ask）。
 *  - 不在这里做任何判断或答案：答不答、怎么答，都由 agent 与它的审核决定。
 *  - 长度在这里先截一刀只是为了不白发；真正的上限在 agent（models.RETELL_LIMIT）。
 */
import { el } from '../core/dom.js';

/** 与 agent 的 SAY_LIMIT 同量级：一个问题不需要更长，更长的多半是粘贴。 */
export const QUESTION_MAX = 80;

/**
 * 读者打的字 → 要发出去的问题。空白、只有标点的不发。
 * 纯函数，不碰 DOM，测试直接用。
 */
export function cleanQuestion(raw) {
  const text = String(raw ?? '').replace(/\s+/g, ' ').trim().slice(0, QUESTION_MAX);
  if (!text) return null;
  // 全是标点/符号（如“？？？”）没有可回答的内容
  if (!/[\p{L}\p{N}]/u.test(text)) return null;
  return text;
}

let mounted = false;
/** 样式只挂一次。不在 import 时碰 document（node 测试要能加载本模块）。 */
function mountStyle() {
  if (mounted || typeof document === 'undefined') return;
  mounted = true;
  if (document.getElementById('ask-css')) return;
  document.head.append(el('link', { id: 'ask-css', rel: 'stylesheet', href: '/src/styles/ask.css' }));
}

/**
 * @param {object} p
 * @param {(action: string, args: object, out: HTMLElement) => Promise<unknown>} p.ask  env.ask：把回答渲染进 out
 * @param {string} [p.label] 输入框的无障碍名称
 */
export function askBox({ ask, label = '我想问' }) {
  mountStyle();
  const input = el('input', { type: 'text', class: 'ask-input', maxlength: String(QUESTION_MAX),
    'aria-label': label, placeholder: '比如：他为什么哭？', autocomplete: 'off', enterkeyhint: 'send' });
  const out = el('div', { class: 'ask-answer', 'aria-live': 'polite' });
  const send = el('button', { class: 'btn primary', type: 'submit', text: '问' });
  let busy = false;

  const form = el('form', { class: 'ask-box', role: 'search', 'aria-label': label,
    onsubmit: async e => {
      e.preventDefault();
      if (busy) return;
      const text = cleanQuestion(input.value);
      if (!text) { input.focus(); return; }
      busy = true; send.disabled = true;
      input.value = '';                       // 发出去就清空：这里不留孩子的原话
      try { await ask('free_text', { text }, out); }
      finally { busy = false; send.disabled = false; }
    } }, input, send);

  return el('div', { class: 'ask' }, form, out);
}
