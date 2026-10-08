/** @deprecated Use page-friction — kept for catalog-crawl import stability. */
import { parsePageFrictionPayload } from '../page-friction/detect.js';
export { PAGE_FRICTION_JS as AUTH_GATE_JS } from '../page-friction/detect.js';
export function parseAuthGatePayload(raw) {
    const report = parsePageFrictionPayload(raw);
    if (!report)
        return null;
    return {
        needsAuth: report.kinds.includes('login') || report.kinds.includes('paywall'),
        captcha: report.kinds.includes('captcha') || report.kinds.includes('human_verify'),
        url: report.url,
        title: report.title,
    };
}
