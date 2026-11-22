import { describe, it, expect } from 'vitest'
import { sanitizeNickname, isNicknameAllowed, isNicknameBlocked, normalizeForBlocklist } from '../src'

describe('sanitizeNickname', () => {
  it('去首尾空白', () => expect(sanitizeNickname('  海鸥 ', 'x')).toBe('海鸥'))
  it('去控制字符', () => expect(sanitizeNickname('海\u0000鸥\n', 'x')).toBe('海鸥'))
  it('超过 12 个字符回退', () => expect(sanitizeNickname('一二三四五六七八九十一二三', '玩家 1')).toBe('玩家 1'))
  it('12 个字符按码点计（emoji 算 1 个）', () => expect(sanitizeNickname('🐟'.repeat(12), 'x')).toBe('🐟'.repeat(12)))
  it('空串与非字符串回退', () => { expect(sanitizeNickname('   ', '玩家 2')).toBe('玩家 2'); expect(sanitizeNickname(42, '玩家 2')).toBe('玩家 2') })
})

describe('isNicknameAllowed（屏蔽词）', () => {
  it('保留字前缀拒绝（防止冒充电脑与官方）', () => {
    for (const n of ['电脑1', '机器人', '系统消息', '官方客服', '管理员小王', 'Admin', 'GM01', ' 电脑']) expect(isNicknameAllowed(n)).toBe(false)
  })
  it('评审：bot 前缀同样拒绝（含分隔符与全角变体）', () => {
    for (const n of ['bot1号', 'bot:9527', 'ＢＯＴ小明', 'b o t 阿明']) expect(isNicknameAllowed(n)).toBe(false)
    expect(isNicknameAllowed('rabbit跳')).toBe(true) // 只按前缀拦
  })
  it('含 🤖 拒绝', () => expect(isNicknameAllowed('小🤖')).toBe(false))
  it('脏词包含匹配，绕过分隔符、全角与零宽字符', () => {
    for (const n of ['傻逼', '大傻·逼', 'ＦＵＣＫ', 'f u c k', 'f.u.c.k', 'sh\u200bit', 'SHIT', '你好操你']) expect(isNicknameAllowed(n)).toBe(false)
  })
  it('正常昵称通过', () => {
    for (const n of ['敏捷的海鸥', '沉默的狐狸', '电工老李', '玩家 1']) expect(isNicknameAllowed(n)).toBe(true)
  })
  it('保留字只按前缀：中间出现“电脑”不拦', () => expect(isNicknameAllowed('我的电脑')).toBe(true))
  it('非字符串拒绝', () => { expect(isNicknameAllowed(42)).toBe(false); expect(isNicknameAllowed(undefined)).toBe(false) })
  it('sanitizeNickname 本身不做屏蔽', () => expect(sanitizeNickname('电脑1', 'x')).toBe('电脑1'))
})

describe('normalizeForBlocklist', () => {
  it('NFKC、小写、去空白/分隔符/零宽字符', () => {
    expect(normalizeForBlocklist('ＦＵＣＫ')).toBe('fuck')
    expect(normalizeForBlocklist('A d·m._i-n*\u3000\u200b')).toBe('admin')
  })
  it('isNicknameBlocked 与 isNicknameAllowed 互补', () => {
    expect(isNicknameBlocked('GM01')).toBe(true)
    expect(isNicknameBlocked('海鸥')).toBe(false)
  })
})
