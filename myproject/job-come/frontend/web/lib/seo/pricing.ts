/**
 * Pricing facts the public pages state out loud.
 *
 * These restate backend constants — `jc.services.membership_service.MONTHLY_PRICE_CNY` /
 * `MONTHLY_DAYS`, `jc.services.mock_quota_service.FREE_FULL_RUNS_PER_MONTH`, and the
 * once-per-account free download enforced by `User.free_download_used_at` — as the
 * sentences a reader actually sees ("每月 1 次", not `1`).
 *
 * They are centralized because a public claim is the one copy error a reader can hold
 * us to. Writing 永久免费 or 无水印 here would be false: free exports carry an
 * attribution line (`resume_render_engine.WATERMARK_TEXT`) and free downloads are
 * once per account. If the backend changes a limit, change it here and in
 * `app/membership-terms/page.tsx`, which states the same terms in legal language.
 */

export const MEMBERSHIP_PRICE_CNY = 25;
export const MEMBERSHIP_DAYS = 30;
export const FREE_MOCK_RUNS_PER_MONTH = 1;
export const FREE_DOWNLOADS_PER_ACCOUNT = 1;

export const MEMBERSHIP_PRICE_TEXT = `${MEMBERSHIP_PRICE_CNY} 元 / ${MEMBERSHIP_DAYS} 天`;
export const FREE_MOCK_RUNS_PER_MONTH_TEXT = `${FREE_MOCK_RUNS_PER_MONTH} 次`;
export const FREE_DOWNLOADS_PER_ACCOUNT_TEXT = `每个账号可免费下载 ${FREE_DOWNLOADS_PER_ACCOUNT} 次`;
