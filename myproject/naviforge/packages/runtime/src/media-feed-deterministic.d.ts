import type { DomSnapshot } from '@naviforge/dom-plane';
import type { AgentCtx } from './agent-ctx.js';
import type { PageState } from './page-state.js';
/** @deprecated import from media-home-harvest — kept for re-export */
export declare function pickFeedClickIndex(snap: DomSnapshot, pageState?: PageState | null): number | undefined;
/**
 * Generic media candidate smoke path. It deliberately does not trust a
 * non-empty structured extract: navigation/category rows are not media rows.
 * Candidate selection comes from Page State/snapshot, click effect is
 * verified generically (post-action-verify), and Network observes the
 * resulting request. If the first click lands on a detail-like page but no
 * media request appears, a second generic "play control" click is tried
 * before giving up — real players often require an explicit play action.
 */
export declare function tryMediaFeedDeterministicHarvest(ctx: AgentCtx): Promise<string | undefined>;
