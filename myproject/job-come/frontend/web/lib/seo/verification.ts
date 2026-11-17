/**
 * Search engine ownership tokens, empty until each console hands one out.
 *
 * Verification is what turns "we exist" into "we are submitting sitemaps and reading
 * coverage reports". Without it a site only gets indexed by accident — and a crawl
 * that happens by accident reports nothing back to us, so "怎么都收录不了" stays
 * undiagnosable. These env vars exist so the tokens go into production config and
 * never into the repo: a verification tag is public, but it is still an ownership
 * claim, and a token in git cannot be rotated without a commit.
 *
 * `verificationMeta` renders as plain `<meta name=... content=...>` tags. Next's
 * built-in `verification` metadata key covers google/bing/yandex only, so Baidu (and
 * Bing's alternative spelling) go through here for uniformity.
 */

/** Google Search Console → 属性 → 添加资源 → 网域, DNS TXT record (not an HTML tag). */
export const GSC_SITE_VERIFICATION =
  process.env.NEXT_PUBLIC_GSC_SITE_VERIFICATION?.trim() ?? "";

/** 百度搜索资源平台 → 资源验证 → HTML 标签验证. */
export const BAIDU_SITE_VERIFICATION =
  process.env.NEXT_PUBLIC_BAIDU_SITE_VERIFICATION?.trim() ?? "";

/** Bing Webmaster Tools (also feeds DuckDuckGo's index). */
export const BING_SITE_VERIFICATION =
  process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION?.trim() ?? "";

/** Yandex Webmaster — its own crawler reads it; harmless elsewhere. */
export const YANDEX_SITE_VERIFICATION =
  process.env.NEXT_PUBLIC_YANDEX_SITE_VERIFICATION?.trim() ?? "";

/** Baidu pushes sitemaps via its own API with a push token, not via this tag. */
export const BAIDU_PUSH_TOKEN = process.env.NEXT_PUBLIC_BAIDU_PUSH_TOKEN?.trim() ?? "";

export const verificationMeta: Record<string, string> = Object.fromEntries(
  Object.entries({
    "baidu-site-verification": BAIDU_SITE_VERIFICATION,
    "msvalidate.01": BING_SITE_VERIFICATION,
    "yandex-verification": YANDEX_SITE_VERIFICATION,
  }).filter(([, value]) => value.length > 0),
);

export const googleVerification = GSC_SITE_VERIFICATION.length > 0
  ? { google: GSC_SITE_VERIFICATION }
  : undefined;
