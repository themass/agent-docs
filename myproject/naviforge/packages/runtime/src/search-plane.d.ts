import type { ToolResult } from '@naviforge/shared';
export type SearchHit = {
    title: string;
    url: string;
    snippet: string;
};
/** External web search — implemented in the extension (HTTP API). Runtime stays Chrome-free. */
export interface SearchPlane {
    search(query: string, n?: number): Promise<ToolResult<{
        results: SearchHit[];
    }>>;
}
export declare function formatWebSearchTrace(data: unknown): string;
