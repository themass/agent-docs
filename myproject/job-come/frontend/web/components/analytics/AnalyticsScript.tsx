import { ANALYTICS_DOMAIN, ANALYTICS_SRC } from "@/lib/analytics";

/**
 * Pageview analytics, rendered only when configured.
 *
 * An empty `ANALYTICS_SRC` (the default) means no third-party script appears in the
 * HTML at all — no cookie, no consent interaction, nothing the privacy policy has to
 * explain. Set `NEXT_PUBLIC_ANALYTICS_SRC` (plus `NEXT_PUBLIC_ANALYTICS_DOMAIN` for
 * Plausible-style vendors that key by domain) in the deploy env to turn it on; like
 * every `NEXT_PUBLIC_*` value it is compiled in at build time, so `deploy.sh` has to
 * re-run for a change to take effect.
 */
export function AnalyticsScript() {
  if (!ANALYTICS_SRC) return null;
  return (
    <script
      defer
      src={ANALYTICS_SRC}
      {...(ANALYTICS_DOMAIN ? { "data-domain": ANALYTICS_DOMAIN } : {})}
    />
  );
}
