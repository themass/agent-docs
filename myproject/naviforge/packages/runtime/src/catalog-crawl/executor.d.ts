import type { AgentCtx } from '../agent-ctx.js';
import type { CatalogCrawlResult, CatalogCrawlSpec } from './types.js';
/** Deterministic multi-section listing crawl — vertical-agnostic. */
export declare function runCatalogCrawl(ctx: AgentCtx, spec: CatalogCrawlSpec): Promise<CatalogCrawlResult | null>;
