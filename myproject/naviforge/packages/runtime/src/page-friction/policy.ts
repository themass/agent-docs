import type { PageFrictionKind, PageFrictionReport } from './types.js'

const HITL_KINDS: PageFrictionKind[] = ['captcha', 'human_verify', 'login', 'paywall']

export function formatPageFrictionForPrompt(report: PageFrictionReport): string {
  const lines = [
    `PAGE FRICTION (${report.url})`,
    `title: ${report.title || '(untitled)'}`,
    `kinds: ${report.kinds.join(', ') || 'none'}`,
    report.blocking ? 'status: BLOCKING — pause automation' : 'status: advisory',
  ]
  return lines.join('\n')
}

export function frictionGuidanceNotes(report: PageFrictionReport): string[] {
  const notes: string[] = []
  if (report.kinds.includes('captcha') || report.kinds.includes('human_verify')) {
    notes.push(
      'CONSTRAINT: 人机验证 — 调用 system_captcha_wait，用户在浏览器手动完成；禁止自动打码/绕过（Skyvern/OpenHands 同款 HITL）。'
    )
  }
  if (report.kinds.includes('login') || report.kinds.includes('paywall')) {
    notes.push(
      'CONSTRAINT: 登录/付费墙 — skill_load friction；用户在浏览器登录后回复；禁止伪造 cookie/token。'
    )
  }
  if (report.kinds.includes('rate_limit')) {
    notes.push(
      'CONSTRAINT: 限频 — dom_wait ≥5s 后重试；勿高频 navigate/network_read；可 system_ask_user 确认是否继续。'
    )
  }
  if (report.kinds.includes('geo_block') || report.kinds.includes('access_denied')) {
    notes.push('CONSTRAINT: 访问受限 — 勿硬爬；system_done 说明 ENV_BLOCKED 原因。')
  }
  if (report.kinds.includes('cookie_banner') && !report.blocking) {
    notes.push('GUIDANCE: Cookie 横幅 — 可 dom_click 接受（非阻塞）后继续。')
  }
  return notes
}

export function frictionHitlQuestion(report: PageFrictionReport): string | undefined {
  if (report.kinds.includes('captcha') || report.kinds.includes('human_verify')) {
    return '页面出现人机验证。请在浏览器中手动完成验证，完成后回复「完成」。'
  }
  if (report.kinds.includes('login') || report.kinds.includes('paywall')) {
    return '页面需要登录或会员权限。请在浏览器完成登录/授权后回复「已就绪」。'
  }
  if (report.kinds.includes('rate_limit')) {
    return '站点提示访问过于频繁。请稍等片刻或在浏览器确认页面恢复后回复「继续」。'
  }
  return undefined
}

export function shouldAutoHitl(report: PageFrictionReport): boolean {
  return report.kinds.some((k) => HITL_KINDS.includes(k))
}

export function frictionHitlKey(report: PageFrictionReport): string {
  const primary = report.kinds.find((k) => HITL_KINDS.includes(k)) ?? report.kinds[0] ?? 'none'
  return `${report.url}|${primary}`
}
