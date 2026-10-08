import type { DomSnapshot } from '@naviforge/dom-plane';
export type IndexedSnapshotLine = {
    index: number;
    title: string;
};
/** Parse `*[n] title` / `[n] title` rows from any snapshot (host-agnostic). */
export declare function parseIndexedSnapshotLines(snap: Pick<DomSnapshot, 'header' | 'content' | 'footer'>, limit?: number): IndexedSnapshotLine[];
export declare function isNavLikeFeedTitle(title: string): boolean;
