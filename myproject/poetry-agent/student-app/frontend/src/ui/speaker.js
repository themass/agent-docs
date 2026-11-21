/** Always show who is speaking. A poet line also says it is role-play; this is not optional chrome. */
import { el } from '../core/dom.js';
import { kindBadge } from './trust.js';

export const ROLE_NAME = { guide: '向导', narrator: '讲解员' };

export function speakerBar({ role, name }) {
  const label = role === 'poet' ? (name || '诗人') : (ROLE_NAME[role] || '向导');
  return el('div', { class: `speaker speaker--${role}`, role: 'status' },
    el('span', { class: 'seal', 'aria-hidden': 'true', text: label.slice(0, 1) }),
    el('span', { class: 'speaker-name', text: label }),
    role === 'poet' ? el('span', { class: 'tag tag--drama', text: '角色扮演' }) : null);
}

export function agentBubble(reply, { poetName, onBasis } = {}) {
  const role = reply.role || 'guide';
  const tag = reply.via === 'local' ? '本机整理' : reply.source === 'llm' ? 'AI 改写' : '脚本';
  const kindClass = { FACT: 'basis--fact', INTERPRETATION: 'basis--interp', DRAMATIZATION: 'basis--drama' }[reply.badge] || '';
  return el('div', { class: `bubble bubble--${role} ${kindClass}` },
    speakerBar({ role, name: poetName }),
    el('p', { class: 'bubble-say', text: reply.say }),
    reply.badge && reply.badge !== 'NONE' ? kindBadge(reply.badge) : null,
    el('span', { class: 'src-tag soft', text: tag }));
}
