// 前端预检,规则与后端一致(A-contract §3.2);后端为准,这里只为更早、更清楚地提示。

/** 署名不得像 agent:匹配即拒绝。注意该规则按子串匹配,含 "ai" 的真实署名(如 Kai)也会被拒,
 *  这是后端规则的已知副作用,界面在报错时说明。 */
const AGENT_LIKE = /agent|bot|deerflow|system|mcp|llm|ai/i;

export function validateSignature(value: string): string | null {
  const v = value.trim();
  if (v === '') return '署名必填。';
  if (v.length < 2 || v.length > 100) return '署名长度需为 2–100 个字符。';
  if (AGENT_LIKE.test(v)) {
    return '署名不能像 agent 或系统账号(含 agent、bot、deerflow、system、mcp、llm、ai 等字样)。请用真实审核人姓名,必要时改用全名或拼音全拼。';
  }
  return null;
}

export function looksLikeAgent(value: string): boolean {
  return AGENT_LIKE.test(value);
}

const PLACEHOLDERS = ['待核查', '待人工', '未核对', 'tbd'];

export function validateLocator(value: string): string | null {
  const v = value.trim();
  if (v === '') return 'locator 必填(例如卷/页/篇名),不能留空。';
  if (v.length > 300) return 'locator 不能超过 300 个字符。';
  if (v === '空' || PLACEHOLDERS.some(p => v.toLowerCase().includes(p))) {
    return 'locator 不能是占位词(空、待核查、待人工、未核对、TBD)。请填写你亲自核对过的真实定位。';
  }
  return null;
}
