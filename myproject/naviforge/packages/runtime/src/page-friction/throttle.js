/** Global navigation spacing — any page, any task. ponytail: in-process; upgrade for multi-tab shared budget. */
const MIN_NAV_INTERVAL_MS = 450;
const RATE_LIMIT_BACKOFF_MS = 5_000;
let lastNavAt = 0;
let rateLimitUntil = 0;
export async function throttlePageNavigation(opts) {
    const now = Date.now();
    if (opts?.rateLimited)
        rateLimitUntil = now + RATE_LIMIT_BACKOFF_MS;
    const floor = Math.max(lastNavAt + MIN_NAV_INTERVAL_MS, rateLimitUntil);
    const wait = floor - now;
    if (wait > 0)
        await new Promise((r) => setTimeout(r, wait));
    lastNavAt = Date.now();
}
export function markPageRateLimited() {
    rateLimitUntil = Date.now() + RATE_LIMIT_BACKOFF_MS;
}
export function resetPageThrottleForTests() {
    lastNavAt = 0;
    rateLimitUntil = 0;
}
