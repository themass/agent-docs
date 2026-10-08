/** Snapshot of the tools[] block sent to the model — audit/UI only. */
export function buildToolCatalog(tools) {
    return tools.map((tool) => ({
        name: tool.function.name,
        description: tool.function.description ?? '',
        source: tool.function.name.startsWith('mcp__') ? 'mcp' : 'builtin',
    }));
}
