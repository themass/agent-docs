import type { AgentCtx } from './agent-ctx.js';
import type { DomPlane } from '@naviforge/dom-plane';
import type { NetworkPlane } from '@naviforge/network-plane';
import { type PageSignalsBundle } from '@naviforge/observe';
import type { PageBrief } from './catalog-crawl/page-role.js';
export type ScriptBodyPreview = {
    url: string;
    preview: string;
};
export declare function hydratePageSignals(opts: {
    dom: DomPlane;
    network?: NetworkPlane;
    url: string;
    scriptBodies?: ScriptBodyPreview[];
}): Promise<{
    text: string;
    bundle: PageSignalsBundle;
}>;
/** List/catalog pages expose detail links; streams live on play/detail pages. */
export declare function formatListPageMediaHint(bundle: PageSignalsBundle, task: string, brief?: PageBrief): string | undefined;
export declare function applyPageSignalsToCtx(ctx: AgentCtx, opts?: {
    url?: string;
    scriptBodies?: ScriptBodyPreview[];
    pageBrief?: PageBrief;
}): Promise<PageSignalsBundle | null>;
export declare function isMediaEvidenceTask(task: string): boolean;
/** E / F6: high-confidence resolved playback → skip model when unambiguous single-item task. */
export declare function tryMediaPlaybackDeterministicResult(bundle: PageSignalsBundle, task: string, opts?: {
    strategy?: 'media-extract' | 'spawn-media' | 'current-page-list' | 'full-catalog' | 'delegate-model';
}): string | undefined;
export declare function formatPlaybackCandidatesForHitl(bundle: PageSignalsBundle): string | undefined;
