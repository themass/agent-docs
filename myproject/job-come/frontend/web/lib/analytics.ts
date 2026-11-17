/**
 * Analytics, off by default.
 *
 * The reason this exists at all: every SEO question we cannot answer today is a
 * question about data we never collected — which page gets crawled, which query
 * brought someone here, where they left. `NEXT_PUBLIC_ANALYTICS_SRC` being unset
 * means no third-party script loads, no cookie is set, and the consent banner stays
 * silent (it is mounted only when an ad client id is configured, see
 * `components/consent/ConsentBanner`).
 *
 * This is deliberately analytics, not advertising: AdSense (`lib/legal.ts
 * ADSENSE_CLIENT`) is a separate switch that does require consent, and the privacy
 * policy already commits to asking before any advertising cookie is used.
 *
 * `track()` is a no-op when analytics is off, so call sites do not need to know.
 */

export const ANALYTICS_SRC = process.env.NEXT_PUBLIC_ANALYTICS_SRC?.trim() ?? "";

/** Plausible-style deployments key the site by domain; other vendors leave this unset. */
export const ANALYTICS_DOMAIN = process.env.NEXT_PUBLIC_ANALYTICS_DOMAIN?.trim() ?? "";

/** Events worth naming: page view is automatic, the rest are product moments. */
export const ANALYTICS_EVENT = {
  /** Uploaded a resume from the landing page. The funnel's real first step. */
  HOME_START: "home_start",
  /** Chose a plan on the landing page. */
  PRICING_VIEW: "pricing_view",
} as const;

type TrackFn = (name: string, props?: Record<string, unknown>) => void;

declare global {
  interface Window {
    /** Plausible-style API. Other vendors expose different names; extend when added. */
    plausible?: TrackFn;
    dataLayer?: unknown[];
  }
}

export function track(name: string, props?: Record<string, unknown>): void {
  if (typeof window === "undefined") return;
  try {
    window.plausible?.(name, props ? { props } : undefined);
  } catch {
    // Analytics must never break the flow it is measuring.
  }
}
