import type { PageFrictionKind, PageFrictionReport } from './types.js'

/**
 * Universal page friction probe — runs on any page after navigation/read.
 * Site-agnostic; complements network 429 and policy HITL (system_captcha_wait).
 */
export const PAGE_FRICTION_JS = `(() => {
  const title = (document.title || '').toLowerCase()
  const path = (location.pathname || '').toLowerCase()
  const text = (document.body?.innerText || '').slice(0, 5000).toLowerCase()
  const blob = title + ' ' + path + ' ' + text

  const kinds = []
  const hasPassword = Boolean(document.querySelector('input[type=password]'))
  const loginish = /login|sign[\\s-]?in|register|sign[\\s-]?up|auth|登录|注册|帐号|账号/.test(blob)
  if (hasPassword && loginish) kinds.push('login')

  const captchaDom = Boolean(
    document.querySelector(
      '[class*="captcha"],[id*="captcha"],iframe[src*="captcha"],[class*="geetest"],[class*="turnstile"],#challenge-form,[data-sitekey]'
    )
  )
  const captchaText = /captcha|验证码|人机|verify you are human|security check|滑动验证|点选|unusual traffic|are you a robot/.test(
    blob
  )
  if (captchaDom || captchaText) kinds.push('captcha')
  if (/verify you are human|checking your browser|just a moment|请完成验证|安全验证/.test(blob)) {
    kinds.push('human_verify')
  }

  if (/too many requests|rate limit|429|访问过于频繁|请求过于频繁|try again later|稍后再试|slow down/.test(blob)) {
    kinds.push('rate_limit')
  }
  if (/not available in your country|地区限制|region|geo.?block|此内容不可|unavailable in your/.test(blob)) {
    kinds.push('geo_block')
  }
  if (/access denied|forbidden|403|拒绝访问|无权访问/.test(blob)) kinds.push('access_denied')

  const cookieBanner = Boolean(
    document.querySelector(
      '#onetrust,[class*="cookie"],[id*="cookie-banner"],[aria-label*="cookie"],[class*="consent-banner"]'
    )
  )
  if (cookieBanner) kinds.push('cookie_banner')

  const paywallMarketing = /subscribe to (watch|read)|会员专享|付费|vip only|开通vip|vip专享|最低仅需|新客低至/.test(blob)
  const paywallHard = /登录后观看|请登录后|sign in to view|unlock this|login to download|请先登录/.test(blob)
  if (paywallMarketing || paywallHard) kinds.push('paywall')

  const hasDownloadCta = /单篇下载|批量下载|立即下载|\\bdownload\\b/.test(blob)
  const blockingKinds = kinds.filter((k) => {
    if (k === 'cookie_banner') return false
    if (k === 'paywall') {
      if (paywallHard || (hasPassword && loginish)) return true
      if (hasDownloadCta && !hasPassword) return false
      return paywallHard
    }
    return true
  })
  return {
    url: location.href,
    title: document.title || '',
    kinds,
    blocking: blockingKinds.length > 0,
    cookieBanner,
  }
})()`

const KIND_SET = new Set<string>([
  'login',
  'captcha',
  'human_verify',
  'rate_limit',
  'geo_block',
  'cookie_banner',
  'paywall',
  'access_denied',
])

export function parsePageFrictionPayload(raw: unknown): PageFrictionReport | null {
  if (!raw || typeof raw !== 'object') return null
  const rec = raw as Record<string, unknown>
  const kinds: PageFrictionKind[] = []
  if (Array.isArray(rec.kinds)) {
    for (const k of rec.kinds) {
      if (typeof k === 'string' && KIND_SET.has(k)) kinds.push(k as PageFrictionKind)
    }
  }
  return {
    url: typeof rec.url === 'string' ? rec.url : '',
    title: typeof rec.title === 'string' ? rec.title : '',
    kinds,
    blocking: Boolean(rec.blocking),
    cookieBanner: Boolean(rec.cookieBanner),
  }
}

/** Text-only fallback when executeJs unavailable (dom_read body). */
export function classifyTextFriction(text: string): PageFrictionKind[] {
  const blob = text.slice(0, 6000).toLowerCase()
  const kinds: PageFrictionKind[] = []
  if (/login|sign in|登录|注册/.test(blob) && /password|密码/.test(blob)) kinds.push('login')
  if (/captcha|验证码|人机|verify you are human|security check/.test(blob)) kinds.push('captcha')
  if (/verify you are human|checking your browser|安全验证/.test(blob)) kinds.push('human_verify')
  if (/too many requests|rate limit|访问过于频繁|429/.test(blob)) kinds.push('rate_limit')
  if (/not available in your country|地区限制/.test(blob)) kinds.push('geo_block')
  if (/access denied|拒绝访问/.test(blob)) kinds.push('access_denied')
  const paywallMarketing = /sign in to view|会员专享|开通vip|vip专享|最低仅需/.test(blob)
  const paywallHard = /登录后观看|请登录后|请先登录|login to download/.test(blob)
  if (paywallMarketing || paywallHard) kinds.push('paywall')
  return kinds
}

/** Marketing VIP copy on an otherwise usable page should not block automation. */
export function isHardPaywall(report: PageFrictionReport): boolean {
  if (!report.kinds.includes('paywall')) return false
  if (report.kinds.includes('login')) return true
  return report.blocking
}
