import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane';
import { type PageListItem } from '@naviforge/extract';
/** Unified extract for `browser_observe extract` / `system_extract_page`. */
export declare function runSystemExtractPage(input: {
    snap: DomSnapshot;
    dom: DomPlane;
    network?: {
        list: (opts: {
            limit?: number;
        }) => Promise<{
            ok: boolean;
            data?: Array<{
                url: string;
                bodyPreview?: string;
            }>;
        }>;
    };
    limit?: number;
}): Promise<{
    items: PageListItem[];
    snap: DomSnapshot;
}>;
export declare function pageListToToolData(items: PageListItem[]): {
    items: PageListItem[];
    count: number;
};
