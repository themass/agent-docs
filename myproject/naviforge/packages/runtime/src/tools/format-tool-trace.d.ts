export declare const READ_PAGE_TRACE_CHARS: 3000;
/** GitHub REST contents listing or JSON-formatter page — extract file names + raw URLs. */
export declare function extractGithubContentsListing(text: string): {
    names: string[];
    rawUrls: string[];
} | null;
export declare function formatGithubContentsEvidence(text: string): string | null;
export declare function formatReadPageTrace(data: unknown): string;
export declare function formatExtractDomTrace(data: unknown): string;
export declare function formatExtractContentTrace(data: unknown): string;
/** Single entry for successful tool trace lines in execTurn and hooks. */
export declare function formatToolTrace(tool: string, data: unknown, args?: Record<string, unknown>): string;
