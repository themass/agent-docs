export type PageFrictionKind =
  | 'login'
  | 'captcha'
  | 'human_verify'
  | 'rate_limit'
  | 'geo_block'
  | 'cookie_banner'
  | 'paywall'
  | 'access_denied'

export type PageFrictionReport = {
  url: string
  title: string
  kinds: PageFrictionKind[]
  /** True when agent should pause automation (not cookie_banner alone). */
  blocking: boolean
  cookieBanner: boolean
}
