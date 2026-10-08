import type { AgentCtx } from '../agent-ctx.js';
import type { CatalogCrawlResult, CatalogCrawlSpec, CatalogDiscoverResult } from './types.js';
/**
 * Extract the current tab only — no section navigation, no pagination hops.
 * Media resolution runs only for a single-item list when resolveMedia=true.
 */
export declare function runCurrentPageListCrawl(ctx: AgentCtx, spec: CatalogCrawlSpec, discover: CatalogDiscoverResult, opts?: {
    resolveMedia?: boolean;
}): Promise<CatalogCrawlResult | null>;
