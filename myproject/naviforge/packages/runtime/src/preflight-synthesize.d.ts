import type { CatalogCrawlResult } from './catalog-crawl/types.js';
import type { CatalogStrategy } from './catalog-crawl/strategy.js';
export type PreflightEvidence = {
    strategy: CatalogStrategy;
    listResult?: string;
    mediaPlayback?: string;
    catalogCrawl?: CatalogCrawlResult | null;
    spawnGuidance?: string;
};
/** Merge preflight evidence; catalog partial beats single-playback shortcut. */
export declare function synthesizePreflightResult(evidence: PreflightEvidence): string | undefined;
