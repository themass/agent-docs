// 昵称屏蔽词：保留字前缀 + 包含匹配的种子脏词表。所有匹配都作用于归一化后的字符串。

/** 以这些词开头的昵称会被拒绝，防止冒充电脑与官方（已归一化：小写）。 */
export const RESERVED_PREFIXES: readonly string[] = ['电脑', '机器人', '系统', '官方', '管理员', 'admin', 'gm', 'bot']

/** 出现在昵称任意位置即拒绝。 */
export const RESERVED_CONTAINS: readonly string[] = ['🤖']

// TODO(P5): 这只是一份很短的种子表。公开上线前必须换成经授权、人工审核过的正式词库。
export const PROFANITY: readonly string[] = ['傻逼', '操你', 'fuck', 'shit']

// NFKC 之后仍需单独去掉的字符：空白、分隔符 ·._-*、零宽字符、控制字符。
const STRIP = /[\s\p{Cc}\u200B-\u200F\u2060\uFEFF\u00B7._\-*]/gu

/** NFKC（全角转半角）→ 小写 → 去空白、分隔符、零宽与控制字符。 */
export function normalizeForBlocklist(s: string): string {
  return s.normalize('NFKC').toLowerCase().replace(STRIP, '')
}

export function isNicknameBlocked(nickname: string): boolean {
  const n = normalizeForBlocklist(nickname)
  if (RESERVED_PREFIXES.some((p) => n.startsWith(p))) return true
  if (RESERVED_CONTAINS.some((w) => n.includes(w))) return true
  return PROFANITY.some((w) => n.includes(w))
}
