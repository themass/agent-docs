/**
 * Operator details shown in the footer and legal pages.
 *
 * LEGAL_DRAFT is the switch for the draft notice on the legal pages. It is off: the
 * operator entity, contact details and refund terms are set.
 */
export const LEGAL_DRAFT = false;

export const OPERATOR_NAME = process.env.NEXT_PUBLIC_OPERATOR_NAME?.trim() || "【主体名称待填写】";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || "【联系邮箱待填写】";
export const LEGAL_UPDATED = "2026 年 11 月 2 日";

/** Google AdSense publisher id. Empty until the account is approved; no ad code loads without it. */
export const ADSENSE_CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT?.trim() || "";
