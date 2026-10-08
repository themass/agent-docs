export type PageVisit = {
    urlKey: string;
    revision?: number;
    visitedAt: number;
};
/** Stable URL key for dedupe (origin + pathname, no query). */
export declare function pageUrlKey(url: string): string;
export declare function tabsOpenDedupeKey(url: string): string;
export declare function recordPageVisit(visits: Map<string, PageVisit>, url: string, revision?: number): void;
export declare function pageAlreadyVisited(visits: Map<string, PageVisit>, url: string, revision?: number): boolean;
export declare function isRedundantTabsOpen(visits: Map<string, PageVisit>, targetUrl: string, currentUrl: string): boolean;
