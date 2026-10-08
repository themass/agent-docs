import type { CatalogCrawlSpec } from './types.js';
/** Multi-section × multi-page site crawl (video, blog, shop, news…). */
export declare function isCatalogCrawlTask(task: string): boolean;
export declare function parseCatalogCrawlSpec(task: string): CatalogCrawlSpec;
/**
 * Full browser catalog SOP: categories → paginated lists → detail (incl. multi-hop) → validate.
 * Broader than isCatalogCrawlTask (includes single-list-page + per-item detail fields).
 */
export declare function isSiteCatalogSopTask(task: string): boolean;
