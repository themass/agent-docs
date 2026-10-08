/** Resolve public catalog tools to internal builtin handler ids. */
export declare function resolveBuiltinToolCall(tool: string, args: Record<string, unknown>): {
    tool: string;
    arguments: Record<string, unknown>;
};
/** Expand model-facing meta tools (and leftover aliases) to atomic handler ids. */
export declare function expandAgentToolCall(tool: string, args: Record<string, unknown>): {
    tool: string;
    arguments: Record<string, unknown>;
};
