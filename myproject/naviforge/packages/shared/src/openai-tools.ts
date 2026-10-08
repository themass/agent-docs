import { AGENT_TOOL_CATALOG, modelFacingToolIds } from './agent-tools.js'
import { mcpQualifiedName } from './mcp-names.js'

/** OpenAI-compatible function tool definition. */
export type OpenAiFunctionTool = {
  type: 'function'
  function: {
    name: string
    description: string
    parameters: Record<string, unknown>
  }
}

export type McpToolForSchema = {
  serverId: string
  name: string
  description?: string
  inputSchema: unknown
}

/** Maximum MCP tools visible to one model call. */
export const MAX_EXPOSED_MCP_TOOLS = 30

/** Loose object schema — providers validate; Runtime still checks args. */
const LOOSE_OBJECT: Record<string, unknown> = {
  type: 'object',
  properties: {},
  additionalProperties: true,
}

/** Tight schemas for high-traffic meta tools. */
const META_SCHEMAS: Record<string, Record<string, unknown>> = {
  skill_load: {
    type: 'object',
    properties: {
      id: { type: 'string', description: 'Skill id without @version' },
    },
    required: ['id'],
  },
  system_done: {
    type: 'object',
    properties: { result: { type: 'string' } },
    required: ['result'],
  },
  system_ask_user: {
    type: 'object',
    properties: { question: { type: 'string' } },
    required: ['question'],
  },
  system_spawn_readonly_tasks: {
    type: 'object',
    properties: {
      subtasks: {
        type: 'array',
        minItems: 1,
        maxItems: 3,
        description:
          'Preferred (DeerFlow-style): 1–3 parallel readonly workers. Each needs title + prompt; optional urls[], mode fetch|tab.',
        items: {
          type: 'object',
          properties: {
            title: { type: 'string', description: 'Short label (DeerFlow description)' },
            description: { type: 'string', description: 'Alias for title' },
            prompt: { type: 'string', description: 'Full isolated instructions (DeerFlow prompt)' },
            task: { type: 'string', description: 'Alias for prompt' },
            url: { type: 'string', description: 'Single target URL' },
            urls: { type: 'array', items: { type: 'string' }, description: 'Target URLs' },
            mode: {
              type: 'string',
              enum: ['fetch', 'tab'],
              description: 'fetch=fetch_text static; tab=tabs open + browser_observe for rendered pages',
            },
          },
          required: ['prompt'],
        },
      },
      briefs: {
        type: 'array',
        items: { type: 'string' },
        minItems: 1,
        maxItems: 3,
        description:
          'Legacy: 1–3 self-contained brief strings. Prefer subtasks[] with title+prompt to avoid lost context.',
      },
    },
    additionalProperties: false,
  },
  web_search: {
    type: 'object',
    properties: {
      query: { type: 'string', description: 'Search query' },
      n: { type: 'integer', description: 'Number of results (1-8, default 5)' },
    },
    required: ['query'],
    additionalProperties: false,
  },
  fetch_text: {
    type: 'object',
    properties: {
      url: { type: 'string', description: 'Single HTTPS URL for static text' },
      urls: {
        type: 'array',
        items: { type: 'string' },
        minItems: 1,
        maxItems: 10,
        description: 'Batch up to 10 HTTPS URLs in one call (parallel fetch)',
      },
      max_chars: {
        type: 'integer',
        description: 'Max characters to return per URL (default 32000, max 120000)',
      },
    },
    additionalProperties: false,
  },
  workspace: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['ls', 'read', 'write', 'mkdir', 'touch', 'stat', 'glob', 'grep', 'script_save', 'script_download'],
      },
      path: { type: 'string' },
      content: { type: 'string' },
      pattern: { type: 'string' },
      glob: { type: 'string' },
      title: { type: 'string' },
      language: { type: 'string', enum: ['python', 'shell', 'javascript'] },
      filename: { type: 'string' },
      id: { type: 'string' },
    },
    required: ['action'],
    additionalProperties: false,
  },
  dom_navigate: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['back', 'forward', 'reload', 'url'],
        description: 'Navigation action; for url must also set url',
      },
      url: { type: 'string', description: 'Required when action is url' },
    },
    required: ['action'],
    additionalProperties: false,
  },
  dom_read: {
    type: 'object',
    properties: {
      mode: {
        type: 'string',
        enum: ['body', 'list', 'dom', 'markdown'],
        description: 'body=article text; list=card rows; dom=links/buttons; markdown=write pages/',
      },
      n: { type: 'integer', description: 'List row limit when mode=list (default 10)' },
      kind: {
        type: 'string',
        enum: ['all', 'links', 'buttons', 'feeds'],
        description: 'dom extract kind when mode=dom',
      },
      limit: { type: 'integer', description: 'dom extract limit when mode=dom' },
      timeout_ms: {
        type: 'integer',
        description: 'Body read timeout in ms when mode=body (default 15000, max 30000)',
      },
    },
    required: ['mode'],
    additionalProperties: false,
  },
  network_read: {
    type: 'object',
    properties: {
      mode: {
        type: 'string',
        enum: ['digest', 'list', 'body', 'media', 'hls', 'wait'],
        description: 'digest=summary; list=events; body=response (id or urlIncludes); media=URLs; hls=playlist; wait=idle',
      },
      limit: { type: 'integer' },
      id: { type: 'string', description: 'Captured request id from mode=list' },
      urlIncludes: { type: 'string', description: 'For body: auto-pick latest captured request whose URL contains this substring' },
      method: { type: 'string' },
      urlRegex: { type: 'string' },
      status: { type: 'integer' },
      timeout_ms: { type: 'integer' },
      text: { type: 'string' },
      baseUrl: { type: 'string' },
    },
    required: ['mode'],
    additionalProperties: false,
  },
  browser_observe: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['snapshot', 'read', 'extract', 'screenshot', 'pdf', 'js', 'probe'],
        description: 'snapshot=a11y; read=body/list/dom/markdown; extract=list+media; js/probe=readonly MAIN',
      },
      mode: {
        type: 'string',
        enum: ['compact', 'viewport', 'full', 'body', 'list', 'dom', 'markdown'],
      },
      n: { type: 'integer' },
      kind: { type: 'string', enum: ['all', 'links', 'buttons', 'feeds'] },
      limit: { type: 'integer' },
      code: { type: 'string' },
      expression: { type: 'string' },
      timeout_ms: { type: 'integer' },
    },
    required: ['action'],
    additionalProperties: false,
  },
  browser_act: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: [
          'click',
          'type',
          'press',
          'select',
          'check',
          'hover',
          'drag',
          'upload',
          'scroll',
          'wait',
          'highlight',
          'mark_topn',
          'mark_items',
          'clear_highlights',
          'inject',
        ],
      },
      index: { type: 'integer' },
      revision: { type: 'integer' },
      selector: { type: 'string' },
      framePath: { type: 'string' },
      text: { type: 'string' },
      key: { type: 'string' },
      modifiers: { type: 'array', items: { type: 'string' } },
      value: { type: 'string' },
      checked: { type: 'boolean' },
      filename: { type: 'string' },
      content_base64: { type: 'string' },
      from_index: { type: 'integer' },
      to_index: { type: 'integer' },
      to: { type: 'string' },
      y: { type: 'integer' },
      direction: { type: 'string' },
      amount: { type: 'integer' },
      kind: { type: 'string', enum: ['stable', 'text', 'network_idle', 'download', 'css', 'html', 'script'] },
      timeout_ms: { type: 'integer' },
      n: { type: 'integer' },
      code: { type: 'string' },
      targets: { type: 'array' },
      items: { type: 'array' },
    },
    required: ['action'],
    additionalProperties: false,
  },
  browser_nav: {
    type: 'object',
    properties: {
      action: { type: 'string', enum: ['back', 'forward', 'reload', 'url'] },
      url: { type: 'string' },
    },
    required: ['action'],
    additionalProperties: false,
  },
  tabs: {
    type: 'object',
    properties: {
      action: { type: 'string', enum: ['list', 'switch', 'close', 'open'] },
      tab_id: { type: 'integer' },
      url: { type: 'string' },
    },
    required: ['action'],
    additionalProperties: false,
  },
  network: {
    type: 'object',
    properties: {
      action: { type: 'string', enum: ['read', 'intercept', 'clear'] },
      mode: { type: 'string', enum: ['digest', 'list', 'body', 'media', 'hls', 'wait'] },
      limit: { type: 'integer' },
      id: { type: 'string' },
      urlIncludes: { type: 'string' },
      method: { type: 'string' },
      urlRegex: { type: 'string' },
      status: { type: 'integer' },
      timeout_ms: { type: 'integer' },
      text: { type: 'string' },
      baseUrl: { type: 'string' },
      rules: { type: 'array' },
    },
    required: ['action'],
    additionalProperties: false,
  },
}

function parametersFromArgsHint(id: string, args: string): Record<string, unknown> {
  if (META_SCHEMAS[id]) return META_SCHEMAS[id]!
  // ponytail: catalog stores compact arg hints, not JSON Schema; expand if providers get picky.
  if (!args || args === '{}') {
    return { type: 'object', properties: {} }
  }
  return LOOSE_OBJECT
}

/** Builtin agent tools as OpenAI `tools[]` entries (aliases excluded). */
export function builtinToolsForApi(only?: readonly string[]): OpenAiFunctionTool[] {
  const ids = modelFacingToolIds(only)
  return ids.map((id) => {
    const tool = AGENT_TOOL_CATALOG.find((item) => item.id === id)!
    return {
      type: 'function',
      function: {
        name: tool.id,
        description: `${tool.description} (${tool.id})`,
        parameters: parametersFromArgsHint(tool.id, tool.args),
      },
    }
  })
}

/** Authorized MCP tools as first-class `mcp__server__tool` function tools. */
export function mcpToolsForApi(tools: McpToolForSchema[] | undefined): OpenAiFunctionTool[] {
  if (!tools?.length) return []
  return tools.slice(0, MAX_EXPOSED_MCP_TOOLS).map((tool) => {
    const schema =
      tool.inputSchema && typeof tool.inputSchema === 'object'
        ? (tool.inputSchema as Record<string, unknown>)
        : LOOSE_OBJECT
    return {
      type: 'function',
      function: {
        name: mcpQualifiedName(tool.serverId, tool.name),
        description: tool.description?.trim() || `MCP ${tool.serverId}.${tool.name}`,
        parameters: schema,
      },
    }
  })
}

/** Full tools list for one planning call. */
export function buildChatTools(
  mcp?: McpToolForSchema[],
  opts?: { only?: readonly string[] }
): OpenAiFunctionTool[] {
  return [...builtinToolsForApi(opts?.only), ...mcpToolsForApi(mcp)]
}
