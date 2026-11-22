/**
 * 随机昵称：“形容词的名词”。词表里的词都不超过 4 个字，
 * 拼起来最长 4 + 1 + 4 = 9 个字符，满足昵称 ≤ 12 的限制。
 */

const ADJECTIVES = [
  '勇敢', '机智', '沉着', '敏捷', '安静', '快乐', '冷静', '神秘',
  '闪亮', '迅捷', '稳健', '好奇', '悠闲', '坚定', '灵巧', '无畏',
] as const

const NOUNS = [
  '海鸥', '信天翁', '飞行员', '领航员', '云雀', '雨燕', '猎鹰', '白鹭',
  '灰雁', '燕子', '雷达兵', '机长', '塔台', '风筝', '热气球', '流星',
] as const

const pick = <T>(list: readonly T[], rng: () => number): T =>
  list[Math.min(list.length - 1, Math.floor(rng() * list.length))]!

export function generateNickname(rng: () => number = Math.random): string {
  return `${pick(ADJECTIVES, rng)}的${pick(NOUNS, rng)}`
}
