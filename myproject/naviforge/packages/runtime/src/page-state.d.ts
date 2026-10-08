import type { DomSnapshot } from '@naviforge/dom-plane';
export type PageStateRole = 'login' | 'list' | 'home' | 'detail' | 'unknown';
export type PageStateItem = {
    title: string;
    url?: string;
    clickIndex?: number;
};
/** Recover cards whose accessibility tree indexes only the image, not its text. */
export declare function extractIndexedMediaCards(snap: Pick<DomSnapshot, 'header' | 'content' | 'footer'>, limit?: number): PageStateItem[];
export type PageState = {
    url: string;
    title: string;
    role: PageStateRole;
    /** Login or captcha wall — do not treat link harvest as site structure. */
    blocked: boolean;
    items: PageStateItem[];
};
export declare function looksLikeLoginUrl(url: string): boolean;
export declare function looksLikeHomeUrl(url: string): boolean;
export declare function classifyPageState(input: {
    url: string;
    title: string;
    login: boolean;
    blocking: boolean;
    items: PageStateItem[];
}): PageState;
/** Merge structured extract with snapshot indices / feed labels (SPA feeds with empty extract). */
export declare function enrichItemsWithSnapshotFeed(items: PageStateItem[], snap: Pick<DomSnapshot, 'header' | 'content' | 'footer'>): PageStateItem[];
export declare function formatPageState(state: PageState): string;
/** Same login page, same link harvest — skip. Page state already describes the wall. */
export declare function shouldSkipLoginLinkRead(input: {
    tool: string;
    args?: Record<string, unknown>;
    page?: PageState | null;
    snapUrl: string;
}): boolean;
