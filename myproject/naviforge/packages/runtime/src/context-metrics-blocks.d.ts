import type { UserPromptBlock } from './prompt.js';
export declare const CONTEXT_METRIC_LABELS: Record<string, string>;
export declare function consolidateUserPromptMetricBlocks(blocks: UserPromptBlock[]): Array<{
    id: string;
    label: string;
    text: string;
}>;
export declare function toolsMetricText(tools: Array<{
    function: {
        name: string;
        description?: string;
    };
}>): string;
