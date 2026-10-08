import type { DomSnapshot } from '@naviforge/dom-plane';
import type { AgentCtx } from './agent-ctx.js';
import type { PageState } from './page-state.js';
export { isLikelyVideoEntryTitle, isTopicBucketSnapshotTitle } from '@naviforge/extract';
/** Section tab that opens a video list (generic UI copy, not a site id). */
export declare function isVideoSectionNavTitle(title: string): boolean;
export declare function pickFeedClickIndex(snap: DomSnapshot, pageState?: PageState | null): number | undefined;
/** Prefer a video card index; else a video section tab; else first non-nav index. */
export declare function pickHomeExploreClickIndex(snap: DomSnapshot, pageState?: PageState | null): number | undefined;
export declare function collectMediaFeedTitles(snap: DomSnapshot, limit?: number): string[];
export type MediaRow = {
    title: string;
    pageUrl?: string;
    streamUrl?: string;
    clickIndex?: number;
};
/** VIDEO rows already merged into PAGE STATE (feed_clicks / click_index). */
export declare function mediaRowsFromPageState(page: PageState | null | undefined, limit?: number): MediaRow[];
export declare function formatMediaHomeHarvestResult(input: {
    rows: MediaRow[];
    shortfall?: string;
}): string;
/**
 * Generic media-home preflight: scroll / section click / extract / network.
 * Never finishes with homepage channel chips only.
 */
export declare function tryMediaHomePreflightDone(ctx: AgentCtx): Promise<string | undefined>;
