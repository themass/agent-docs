export const CONTEXT_METRIC_LABELS = {
    system: 'System prompt',
    skill_catalog: 'Skill catalog',
    tools: 'API parameters (tools[])',
    mcp_tools: 'MCP API parameters',
    task: 'User task',
    reply_language: 'Reply language',
    scope: 'Scope',
    thread: 'Thread / memory',
    skills: 'Loaded skills',
    browser: 'Browser meta',
    url: 'URL',
    title: 'Title',
    frames: 'Frames',
    snapshot: 'Page snapshot',
    network: 'Network',
    trace: 'Trace / summary',
    instruction: 'Instruction',
};
export function consolidateUserPromptMetricBlocks(blocks) {
    const merged = new Map();
    for (const block of blocks) {
        const id = block.name.startsWith('snapshot_') ? 'snapshot' : block.name;
        const bucket = merged.get(id) ?? [];
        bucket.push(block.text);
        merged.set(id, bucket);
    }
    return [...merged.entries()].map(([id, texts]) => ({
        id,
        label: CONTEXT_METRIC_LABELS[id] ?? id,
        text: texts.join('\n\n'),
    }));
}
export function toolsMetricText(tools) {
    return JSON.stringify(tools.map((tool) => ({
        name: tool.function.name,
        description: tool.function.description ?? '',
    })));
}
