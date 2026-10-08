import type { PageSignalsBundle } from '@naviforge/observe';
import type { CatalogDiscoverResult } from './types.js';
export type PageRole = 'list' | 'play' | 'detail' | 'unknown';
/** Lightweight page understanding for strategy selection (no host allowlists). */
export type PageBrief = {
    role: PageRole;
    confidence: number;
    detailShape?: string;
    listItemCount: number;
    hasPlayback: boolean;
    playbackUrl?: string;
    /** Current URL matches the dominant list-item shape (detail / play page). */
    currentMatchesDetailShape: boolean;
};
export declare function detailShapeRegex(shape: string | undefined): RegExp | undefined;
export declare function urlMatchesDetailShape(url: string, shape: string | undefined): boolean;
/** Classify page role from discover voting + PAGE SIGNALS playback evidence. */
export declare function classifyPageBrief(discover: CatalogDiscoverResult, bundle?: PageSignalsBundle | null): PageBrief;
