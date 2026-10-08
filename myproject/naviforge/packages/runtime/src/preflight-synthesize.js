import { formatCatalogCrawlResult } from './catalog-crawl/format.js';
function catalogHasEntries(crawl) {
    return crawl.sections.some((s) => s.pages.some((p) => p.entries.length > 0));
}
function catalogHasMedia(crawl) {
    return crawl.sections.some((s) => s.pages.some((p) => p.entries.some((e) => e.mediaUrl || e.playPageUrl)));
}
/** Merge preflight evidence; catalog partial beats single-playback shortcut. */
export function synthesizePreflightResult(evidence) {
    const { strategy, listResult, mediaPlayback, catalogCrawl, spawnGuidance } = evidence;
    if (catalogCrawl && catalogHasEntries(catalogCrawl)) {
        const body = formatCatalogCrawlResult(catalogCrawl);
        if (spawnGuidance && strategy === 'spawn-media' && !catalogHasMedia(catalogCrawl)) {
            return `${body}\n\n${spawnGuidance}`;
        }
        return body;
    }
    if (strategy === 'media-extract' && mediaPlayback)
        return mediaPlayback;
    if (listResult) {
        return spawnGuidance ? `${listResult}\n\n${spawnGuidance}` : listResult;
    }
    if (mediaPlayback && strategy !== 'spawn-media' && strategy !== 'current-page-list') {
        return mediaPlayback;
    }
    return undefined;
}
