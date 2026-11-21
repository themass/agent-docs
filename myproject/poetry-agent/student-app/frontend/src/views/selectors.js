/**
 * 视图用的纯选择器：只对已经取到的数据做过滤与分档，没有 I/O，也不 import data/。
 * 之所以从 data/ 搬到这里：它们不是数据源，是展示计算（架构规则 A2）。
 */
import { RETELL_LENGTHS } from '../core/vocab.js';

/** 某一层、某一步、某个角色的台词分组。 */
export const groupsOf = (index, step, owner) =>
  index.groups.filter(g => g.step === step && (!owner || g.owner === owner));

/** 复述长度的分档键（事件词表里只有这三档）。 */
export function retellLength(text) {
  const n = [...String(text || '')].length;
  return n <= 20 ? 'len_0_20' : n <= 60 ? 'len_21_60' : 'len_61_plus';
}

/**
 * 首屏的「今天」：只挑一首当主角，不给并列的一排。
 *   1. 有走到一半的诗：它（最近进入的那首）——接着走，比再推一首更有用；
 *   2. 否则：第一首还没碰过的；
 *   3. 否则：列表第一首。
 * 只考虑 hasLesson 的诗。返回 { work, progress } 或 null（列表空：首屏只剩两个门，这是正常状态）。
 */
export function pickToday(works, progressOf) {
  const list = (works || []).filter(w => w && w.hasLesson);
  if (!list.length) return null;
  const withP = list.map(w => ({ work: w, progress: progressOf(w.workId) || null }));
  const going = withP.filter(x => x.progress?.lastStep)
    .sort((a, b) => String(b.progress.enteredAt || '').localeCompare(String(a.progress.enteredAt || '')));
  if (going.length) return going[0];
  return withP.find(x => !x.progress) || withP[0];
}

/**
 * 「今天」那一句。只用服务端给的 hook（内容的一部分，由编辑写、可下架），永远不在前端拼一句关于诗的话。
 * 没有就不显示：宁可少一句，也不让首屏替诗说话。
 */
export const hookOf = work => (typeof work?.hook === 'string' && work.hook.trim() ? work.hook.trim() : null);

/**
 * 「到」的处境句 + 可用的指路。纯函数：只读 bundle 与已有层，不做 I/O。
 *
 * 返回 null（页面回到四张并列卡片）的条件都写成显式判断，因为它们都是正常状态，不是错误：
 *   - 这个 bundle 没有 arrive.situation（旧 bundle）；
 *   - 处境句是 DRAMATIZATION 却没有 badge（trust.js 同一条规则：可能被误当成史料的句子宁可不显示）；
 *   - 一个 choice 指向的层在这一步里不存在（内容没做完，指路就会点空）。
 * choices 为空时仍然返回处境句：一句话本身有价值，只是没有可指的路。
 */
export function situationOf(bundle, availableLayers) {
  const s = bundle?.steps?.find(step => step.step === 'arrive')?.situation;
  if (!s || !s.text) return null;
  if (s.kind === 'DRAMATIZATION' && !s.badge) return null;
  const has = new Set(availableLayers || []);
  const choices = (s.choices || []).filter(c => has.has(c.layer) && c.label);
  return { text: s.text, kind: s.kind, badge: s.badge || null, claimId: s.basis?.claim_id || null, choices };
}
