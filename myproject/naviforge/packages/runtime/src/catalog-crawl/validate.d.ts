import type { CatalogCrawlResult, CatalogValidationReport } from './types.js';
/** Phase 5: dedupe, required-field gaps, light sampling summary. */
export declare function validateCatalogCrawlResult(result: CatalogCrawlResult, opts: {
    wantsMediaUrl: boolean;
}): CatalogValidationReport;
