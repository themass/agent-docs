import type { ToolResult } from '@naviforge/shared';
export type FetchTextResult = {
    url: string;
    status: number;
    content_type: string;
    text: string;
    truncated: boolean;
};
/** Host HTTP GET for static text — implemented in the extension (no tab). Runtime stays Chrome-free. */
export interface FetchPlane {
    fetchText(url: string, maxChars?: number): Promise<ToolResult<FetchTextResult>>;
}
export declare const FETCH_TEXT_DEFAULT_MAX_CHARS = 32000;
export declare const FETCH_TEXT_MAX_CHARS = 120000;
export declare const FETCH_TEXT_MAX_BODY_BYTES = 512000;
export declare function clampFetchMaxChars(n: number | undefined): number;
/** HTTPS-only; no credentials. Network-free for self-check. */
export declare function normalizeFetchTextUrl(raw: string): {
    ok: true;
    url: string;
} | {
    ok: false;
    message: string;
};
export declare function formatFetchTextTrace(data: unknown): string;
