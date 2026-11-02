export type AdsConsent = "granted" | "denied";

const KEY = "jc_consent_ads_v1";

export function getAdsConsent(): AdsConsent | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(KEY);
  return value === "granted" || value === "denied" ? value : null;
}

export function setAdsConsent(value: AdsConsent): void {
  window.localStorage.setItem(KEY, value);
}
