/** One navigational section (category, tag, shop aisle, blog column…). */
export type CatalogSection = {
    name: string;
    url: string;
};
export type MediaPlaybackFormat = 'hls' | 'dash' | 'mp4' | 'webm' | 'embed' | 'unknown';
export type CatalogListEntry = {
    title: string;
    url?: string;
    fields?: Record<string, string>;
    /** Direct stream/download URL (m3u8, mpd, mp4, webm, …). */
    mediaUrl?: string;
    /** When no direct stream: embed / play / iframe page to open or cite. */
    playPageUrl?: string;
    format?: MediaPlaybackFormat;
    confidence?: number;
    shortfall?: string;
};
export type CatalogPageSlice = {
    url: string;
    entries: CatalogListEntry[];
    shortfall?: string;
};
export type CatalogSectionResult = {
    section: CatalogSection;
    pages: CatalogPageSlice[];
    error?: string;
};
/** Discovery output — site-agnostic, no domain allowlists. */
export type CatalogDiscoverResult = {
    url: string;
    origin: string;
    sections: CatalogSection[];
    pagination: Array<{
        label: string;
        url: string;
    }>;
    /** Dominant list-item path shape, e.g. `vod/view/*` or `blog/post/*`. */
    detailShape?: string;
    listSample: Array<{
        title: string;
        url: string;
    }>;
    infiniteScroll?: boolean;
};
export type CatalogCrawlPlan = {
    startUrl: string;
    sections: CatalogSection[];
    detailShape?: string;
    pagesPerSection: number;
    wantsMediaUrl: boolean;
    infiniteScroll?: boolean;
};
export type CatalogCrawlSpec = {
    pagesPerSection: number;
    maxSections: number;
    maxItemsPerPage: number;
    maxMediaFetches: number;
    wantsMediaUrl: boolean;
    wantsTableRows: boolean;
    maxDetailHops: number;
};
export type CatalogValidationReport = {
    totalEntries: number;
    uniqueEntries: number;
    duplicatesRemoved: number;
    missingMedia: number;
    embedOnly: number;
    sampledOk: number;
    issues: string[];
};
export type CatalogCrawlResult = {
    plan: CatalogCrawlPlan;
    sections: CatalogSectionResult[];
    /** True when every planned section×page was visited within budget. */
    complete: boolean;
    truncatedReason?: string;
    validation?: CatalogValidationReport;
    authBlocked?: boolean;
};
