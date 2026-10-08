import type { PageBrief } from './page-role.js';
export type CatalogStrategy = 'media-extract' | 'current-page-list' | 'spawn-media' | 'full-catalog' | 'delegate-model';
export declare function wantsMultipleMediaItems(task: string): boolean;
export declare function selectCatalogStrategy(opts: {
    task: string;
    brief: PageBrief;
    fullSiteCrawl: boolean;
    wantsMedia: boolean;
}): CatalogStrategy;
export declare function spawnMediaGuidance(entryCount: number): string;
