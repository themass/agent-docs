export const FETCH_TEXT_DEFAULT_MAX_CHARS = 32_000;
export const FETCH_TEXT_MAX_CHARS = 120_000;
export const FETCH_TEXT_MAX_BODY_BYTES = 512_000;
export function clampFetchMaxChars(n) {
    if (n == null || !Number.isFinite(n))
        return FETCH_TEXT_DEFAULT_MAX_CHARS;
    return Math.min(FETCH_TEXT_MAX_CHARS, Math.max(1_000, Math.round(n)));
}
/** HTTPS-only; no credentials. Network-free for self-check. */
export function normalizeFetchTextUrl(raw) {
    const trimmed = raw.trim();
    if (!trimmed)
        return { ok: false, message: 'url required' };
    let parsed;
    try {
        parsed = new URL(trimmed);
    }
    catch {
        return { ok: false, message: 'invalid URL' };
    }
    if (parsed.protocol !== 'https:')
        return { ok: false, message: 'HTTPS only' };
    if (parsed.username || parsed.password)
        return { ok: false, message: 'credentials in URL are not allowed' };
    return { ok: true, url: parsed.toString() };
}
export function formatFetchTextTrace(data) {
    const rec = (data ?? {});
    if (Array.isArray(rec.items)) {
        const items = rec.items.filter((item) => !!item && typeof item === 'object');
        const lines = items.slice(0, 8).map((item, index) => {
            const url = typeof item.url === 'string' ? item.url : '';
            if (item.ok === true) {
                const text = typeof item.text === 'string' ? item.text : '';
                const excerpt = text.length > 240 ? `${text.slice(0, 240)}…` : text;
                return `${index + 1}. ok ${url}\n   ${excerpt.replace(/\s+/g, ' ').trim()}`;
            }
            const err = item.error && typeof item.error === 'object' && typeof item.error.message === 'string'
                ? item.error.message
                : 'failed';
            return `${index + 1}. fail ${url} (${err})`;
        });
        return `fetch_text batch ok=${typeof rec.okCount === 'number' ? rec.okCount : items.length}/${items.length}\n${lines.join('\n')}`.slice(0, 8_000);
    }
    const url = typeof rec.url === 'string' ? rec.url : '';
    const status = typeof rec.status === 'number' ? rec.status : 0;
    const contentType = typeof rec.content_type === 'string' ? rec.content_type : '';
    const text = typeof rec.text === 'string' ? rec.text : '';
    const truncated = rec.truncated === true;
    const excerpt = text.length > 4_000 ? `${text.slice(0, 4_000)}\n… (truncated)` : text;
    return `fetch_text ok status=${status} type=${contentType} truncated=${truncated} url=${url}\n${excerpt}`.slice(0, 8_000);
}
