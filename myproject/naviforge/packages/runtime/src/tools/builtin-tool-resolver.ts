/** Resolve public catalog tools to internal builtin handler ids. */
export function resolveBuiltinToolCall(
  tool: string,
  args: Record<string, unknown>
): { tool: string; arguments: Record<string, unknown> } {
  if (tool === 'workspace') return resolveWorkspaceToolCall(args)
  if (tool === 'dom_read') return resolveDomReadToolCall(args)
  if (tool === 'network_read') return resolveNetworkReadToolCall(args)
  return { tool, arguments: args }
}

const NETWORK_READ_MODES = {
  digest: 'network_digest',
  list: 'network_list',
  body: 'network_get_body',
  media: 'network_media_hints',
  hls: 'network_resolve_hls',
  wait: 'network_wait',
} as const

type NetworkReadMode = keyof typeof NETWORK_READ_MODES

function resolveNetworkReadToolCall(args: Record<string, unknown>): { tool: string; arguments: Record<string, unknown> } {
  const mode = args.mode
  if (typeof mode !== 'string' || !(mode in NETWORK_READ_MODES)) {
    return { tool: 'network_read', arguments: args }
  }
  const { mode: _drop, ...rest } = args
  return { tool: NETWORK_READ_MODES[mode as NetworkReadMode], arguments: rest }
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
} as const

type WorkspaceAction = keyof typeof WORKSPACE_ACTION_TOOLS

function resolveWorkspaceToolCall(args: Record<string, unknown>): { tool: string; arguments: Record<string, unknown> } {
  const action = args.action
  if (typeof action !== 'string' || !(action in WORKSPACE_ACTION_TOOLS)) {
    return { tool: 'workspace', arguments: args }
  }
  const { action: _drop, ...rest } = args
  return { tool: WORKSPACE_ACTION_TOOLS[action as WorkspaceAction], arguments: rest }
}

function resolveDomReadToolCall(args: Record<string, unknown>): { tool: string; arguments: Record<string, unknown> } {
  const mode =
    args.mode === 'list' || args.mode === 'dom' || args.mode === 'markdown' || args.mode === 'body'
      ? args.mode
      : 'body'
  if (mode === 'list') {
    const n = typeof args.n === 'number' ? args.n : typeof args.limit === 'number' ? args.limit : 10
    return { tool: 'dom_extract_content', arguments: { n } }
  }
  if (mode === 'dom') {
    return {
      tool: 'dom_extract_dom',
      arguments: {
        kind: args.kind ?? 'all',
        limit: args.limit,
      },
    }
  }
  if (mode === 'markdown') return { tool: 'page_to_markdown', arguments: {} }
  const { timeout_ms } = args
  return {
    tool: 'dom_read_page',
    arguments: typeof timeout_ms === 'number' ? { timeout_ms } : {},
  }
}
