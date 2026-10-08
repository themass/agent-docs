import { urlsMatchForReuse } from './task-classifier.js';
/** Stable URL key for dedupe (origin + pathname, no query). */
export function pageUrlKey(url) {
    try {
        const parsed = new URL(url);
        return `${parsed.origin}${parsed.pathname}`.replace(/\/$/, '');
    }
    catch {
        return url.replace(/\/$/, '');
    }
}
export function tabsOpenDedupeKey(url) {
    return `tabs_open|${pageUrlKey(url)}`;
}
export function recordPageVisit(visits, url, revision) {
    const key = pageUrlKey(url);
    if (!key)
        return;
    visits.set(key, { urlKey: key, revision, visitedAt: Date.now() });
}
export function pageAlreadyVisited(visits, url, revision) {
    const key = pageUrlKey(url);
    const hit = visits.get(key);
    if (!hit)
        return false;
    if (revision == null || hit.revision == null)
        return true;
    return hit.revision === revision;
}
export function isRedundantTabsOpen(visits, targetUrl, currentUrl) {
    const target = pageUrlKey(targetUrl);
    if (!target)
        return false;
    if (urlsMatchForReuse(targetUrl, currentUrl))
        return true;
    return visits.has(target);
}
