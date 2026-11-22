// 昵称清洗：去控制字符与首尾空白，按码点计 1–12 个字符，否则回退。
// 屏蔽词另由 isNicknameAllowed 判断；调用方先 sanitizeNickname，再用 isNicknameAllowed 检查。

import { isNicknameBlocked } from './nickname-blocklist'

const MAX_NICKNAME_LENGTH = 12

/** 昵称是字符串且未命中保留字前缀或屏蔽词。 */
export function isNicknameAllowed(input: unknown): boolean {
  return typeof input === 'string' && !isNicknameBlocked(input)
}

export function sanitizeNickname(input: unknown, fallback: string): string {
  if (typeof input !== 'string') return fallback
  const cleaned = input.replace(/\p{Cc}/gu, '').trim()
  const length = [...cleaned].length
  return length >= 1 && length <= MAX_NICKNAME_LENGTH ? cleaned : fallback
}
