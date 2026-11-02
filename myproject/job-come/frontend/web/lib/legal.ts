/**
 * Operator details shown in the footer and legal pages.
 *
 * LEGAL_DRAFT stays true until the operator entity, contact details and the refund
 * terms have been filled in and reviewed. While it is true, every legal page says so
 * at the top, so a draft cannot be mistaken for a published agreement.
 */
export const LEGAL_DRAFT = true;

export const OPERATOR_NAME = process.env.NEXT_PUBLIC_OPERATOR_NAME?.trim() || "【主体名称待填写】";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim() || "【联系邮箱待填写】";
export const LEGAL_UPDATED = "2026 年 11 月 2 日";

/** Google AdSense publisher id. Empty until the account is approved; no ad code loads without it. */
export const ADSENSE_CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT?.trim() || "";
