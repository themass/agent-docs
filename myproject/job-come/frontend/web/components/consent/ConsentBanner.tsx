"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getAdsConsent, setAdsConsent, type AdsConsent } from "@/lib/consent";
import { ADSENSE_CLIENT } from "@/lib/legal";

/**
 * Asks before any advertising cookie is set. Mounted only when an ad client id is configured,
 * so the page never claims to show ads that are not running.
 */
export function ConsentBanner() {
  const [consent, setConsent] = useState<AdsConsent | null | undefined>(undefined);

  useEffect(() => {
    setConsent(getAdsConsent());
  }, []);

  if (!ADSENSE_CLIENT || consent !== null) return null;

  function decide(value: AdsConsent) {
    setAdsConsent(value);
    setConsent(value);
  }

  return (
    <div
      role="dialog"
      aria-label="广告与 Cookie 同意"
      className="fixed inset-x-3 bottom-3 z-[9000] mx-auto flex max-w-3xl flex-col gap-3 rounded-xl border border-surface-border bg-surface p-4 shadow-card sm:flex-row sm:items-center"
    >
      <p className="flex-1 text-xs leading-relaxed text-ink-600">
        我们使用 Google 广告服务，它可能用 Cookie 展示个性化广告。选择“不同意”后，只展示不基于个人兴趣的广告。
        详见 <Link href="/privacy" className="underline">隐私政策</Link>。
      </p>
      <div className="flex shrink-0 gap-2">
        <button type="button" onClick={() => decide("denied")} className="btn btn-sm btn-ghost">
          不同意
        </button>
        <button type="button" onClick={() => decide("granted")} className="btn btn-sm btn-primary">
          同意
        </button>
      </div>
    </div>
  );
}
