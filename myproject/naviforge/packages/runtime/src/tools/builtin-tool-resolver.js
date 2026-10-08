/** Resolve public catalog tools to internal builtin handler ids. */
function omit(args, ...keys) {
    const next = { ...args };
    for (const key of keys)
        delete next[key];
    return next;
}
export function resolveBuiltinToolCall(tool, args) {
    const expanded = expandAgentToolCall(tool, args);
    if (expanded.tool === 'workspace')
        return resolveWorkspaceToolCall(expanded.arguments);
    if (expanded.tool === 'dom_read')
        return resolveDomReadToolCall(expanded.arguments);
    if (expanded.tool === 'network_read')
        return resolveNetworkReadToolCall(expanded.arguments);
    return expanded;
}
/** Expand model-facing meta tools (and leftover aliases) to atomic handler ids. */
export function expandAgentToolCall(tool, args) {
    if (tool === 'browser_observe')
        return expandObserve(args);
    if (tool === 'browser_act')
        return expandAct(args);
    if (tool === 'browser_nav')
        return { tool: 'dom_navigate', arguments: args };
    if (tool === 'tabs')
        return expandTabs(args);
    if (tool === 'network')
        return expandNetwork(args);
    if (tool === 'workspace')
        return resolveWorkspaceToolCall(args);
    if (tool === 'dom_read')
        return resolveDomReadToolCall(args);
    if (tool === 'network_read')
        return resolveNetworkReadToolCall(args);
    return { tool, arguments: args };
}
function snapshotArgs(args) {
    const mode = args.mode;
    return mode === 'compact' || mode === 'viewport' || mode === 'full' ? { mode } : {};
}
function expandObserve(args) {
    const action = args.action;
    if (action === 'read') {
        return resolveDomReadToolCall({ ...args, mode: typeof args.mode === 'string' ? args.mode : 'body' });
    }
    if (action === 'extract')
        return { tool: 'system_extract_page', arguments: omit(args, 'action') };
    if (action === 'screenshot')
        return { tool: 'dom_screenshot', arguments: {} };
    if (action === 'pdf')
        return { tool: 'page_to_pdf', arguments: {} };
    if (action === 'js') {
        const rest = omit(args, 'action');
        if (typeof rest.expression === 'string' && rest.code == null) {
            rest.code = rest.expression;
            delete rest.expression;
        }
        return { tool: 'dom_execute_js', arguments: rest };
    }
    if (action === 'probe')
        return { tool: 'dom_probe', arguments: omit(args, 'action') };
    if (action === 'snapshot')
        return { tool: 'dom_snapshot', arguments: snapshotArgs(args) };
    if (action === undefined) {
        if (args.mode === 'body' || args.mode === 'list' || args.mode === 'dom' || args.mode === 'markdown') {
            return resolveDomReadToolCall(args);
        }
        return { tool: 'dom_snapshot', arguments: snapshotArgs(args) };
    }
    return { tool: 'browser_observe', arguments: args };
}
const ACT_TOOLS = {
    click: 'dom_click',
    type: 'dom_type',
    press: 'dom_press',
    select: 'dom_select',
    check: 'dom_check',
    hover: 'dom_hover',
    drag: 'dom_drag',
    upload: 'dom_upload',
    scroll: 'dom_scroll',
    wait: 'dom_wait',
    highlight: 'dom_highlight',
    mark_topn: 'dom_mark_topn',
    mark_items: 'dom_mark_items',
    clear_highlights: 'dom_clear_highlights',
    inject: 'dom_inject',
};
function expandAct(args) {
    const action = args.action;
    if (typeof action !== 'string' || !(action in ACT_TOOLS)) {
        return { tool: 'browser_act', arguments: args };
    }
    return { tool: ACT_TOOLS[action], arguments: omit(args, 'action') };
}
const TAB_TOOLS = {
    list: 'tabs_list',
    switch: 'tabs_switch',
    close: 'tabs_close',
    open: 'tabs_open',
};
function expandTabs(args) {
    const action = args.action;
    if (typeof action !== 'string' || !(action in TAB_TOOLS)) {
        return { tool: 'tabs', arguments: args };
    }
    return { tool: TAB_TOOLS[action], arguments: omit(args, 'action') };
}
function expandNetwork(args) {
    const action = args.action;
    if (action === 'intercept')
        return { tool: 'network_intercept', arguments: omit(args, 'action') };
    if (action === 'clear')
        return { tool: 'network_clear_intercepts', arguments: omit(args, 'action') };
    if (action === 'read' || action === undefined || typeof args.mode === 'string') {
        return resolveNetworkReadToolCall(omit(args, 'action'));
    }
    return { tool: 'network', arguments: args };
}
const NETWORK_READ_MODES = {
    digest: 'network_digest',
    list: 'network_list',
    body: 'network_get_body',
    media: 'network_media_hints',
    hls: 'network_resolve_hls',
    wait: 'network_wait',
};
function resolveNetworkReadToolCall(args) {
    const mode = args.mode;
    if (typeof mode !== 'string' || !(mode in NETWORK_READ_MODES)) {
        return { tool: 'network_read', arguments: args };
    }
    const { mode: _drop, ...rest } = args;
    return { tool: NETWORK_READ_MODES[mode], arguments: rest };
}
const WORKSPACE_ACTION_TOOLS = {
    ls: 'workspace_ls',
    read: 'workspace_read',
    write: 'workspace_write',
    mkdir: 'workspace_mkdir',
    touch: 'workspace_touch',
    stat: 'workspace_stat',
    glob: 'workspace_glob',
    grep: 'workspace_grep',
    script_save: 'script_save',
    script_download: 'script_download',
};
function resolveWorkspaceToolCall(args) {
    const action = args.action;
    if (typeof action !== 'string' || !(action in WORKSPACE_ACTION_TOOLS)) {
        return { tool: 'workspace', arguments: args };
    }
    const { action: _drop, ...rest } = args;
    return { tool: WORKSPACE_ACTION_TOOLS[action], arguments: rest };
}
function resolveDomReadToolCall(args) {
    const mode = args.mode === 'list' || args.mode === 'dom' || args.mode === 'markdown' || args.mode === 'body'
        ? args.mode
        : 'body';
    if (mode === 'list') {
        const n = typeof args.n === 'number' ? args.n : typeof args.limit === 'number' ? args.limit : 10;
        return { tool: 'dom_extract_content', arguments: { n } };
    }
    if (mode === 'dom') {
        return {
            tool: 'dom_extract_dom',
            arguments: {
                kind: args.kind ?? 'all',
                limit: args.limit,
            },
        };
    }
    if (mode === 'markdown')
        return { tool: 'page_to_markdown', arguments: {} };
    const { timeout_ms } = args;
    return {
        tool: 'dom_read_page',
        arguments: typeof timeout_ms === 'number' ? { timeout_ms } : {},
    };
}
