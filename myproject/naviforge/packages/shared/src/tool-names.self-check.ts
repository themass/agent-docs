import {
  AGENT_TOOL_CATALOG,
  AGENT_TOOL_IDS,
  builtinToolsForApi,
  modelFacingToolIds,
  mcpQualifiedName,
  parseMcpQualifiedName,
} from './index.js'

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

const builtinPattern = /^[a-z][a-z0-9_]*$/
assert(
  AGENT_TOOL_IDS.every((id) => builtinPattern.test(id)),
  'builtin tool ids must be snake_case'
)
assert(new Set(AGENT_TOOL_IDS).size === AGENT_TOOL_IDS.length, 'builtin tool ids must be unique')
assert(
  AGENT_TOOL_IDS.every((id) => !id.startsWith('mcp__')),
  'builtin tool ids must not use the MCP namespace'
)
assert(
  builtinToolsForApi().every((tool) =>
    modelFacingToolIds().includes(tool.function.name as (typeof AGENT_TOOL_IDS)[number])
  ),
  'OpenAI builtin tools must be model-facing catalog ids'
)
assert(
  modelFacingToolIds().length === AGENT_TOOL_IDS.length,
  'model-facing tools match catalog'
)
assert(AGENT_TOOL_IDS.includes('browser_observe'), 'browser_observe in catalog')
assert(!AGENT_TOOL_IDS.includes('dom_read_page'), 'dom_read_page not in catalog')
assert(AGENT_TOOL_IDS.includes('workspace'), 'workspace in catalog')
assert(!AGENT_TOOL_IDS.includes('workspace_read'), 'workspace_read not in catalog')
assert(modelFacingToolIds().length <= 15, 'model-facing catalog ≤15')
assert(!AGENT_TOOL_IDS.includes('dom_click'), 'atomic dom_click is not model-facing')

const workspaceSchema = builtinToolsForApi().find(
  (tool) => tool.function.name === 'workspace'
)?.function.parameters as { properties?: Record<string, unknown>; additionalProperties?: unknown } | undefined
assert(workspaceSchema?.additionalProperties === false, 'workspace schema rejects unknown fields')
for (const field of ['title', 'language', 'filename', 'id']) {
  assert(field in (workspaceSchema?.properties ?? {}), `workspace schema exposes ${field}`)
}

const browserActSchema = builtinToolsForApi().find(
  (tool) => tool.function.name === 'browser_act'
)?.function.parameters as { additionalProperties?: unknown } | undefined
assert(browserActSchema?.additionalProperties === false, 'browser_act schema rejects unknown fields')

const catalogIds = new Set(AGENT_TOOL_CATALOG.map((tool) => tool.id))
assert(catalogIds.size === AGENT_TOOL_CATALOG.length, 'catalog ids unique')

const collisionA = mcpQualifiedName('a.b', 'tool')
const collisionB = mcpQualifiedName('a_b', 'tool')
assert(collisionA !== collisionB, 'MCP encoding must distinguish dot from underscore')

for (const [server, tool] of [
  ['a.b', 'read.file'],
  ['a_b', 'read_file'],
  ['server__name', 'tool__name'],
  ['服务器', '读取_页面'],
] as const) {
  const wireName = mcpQualifiedName(server, tool)
  assert(/^[A-Za-z0-9_]+$/.test(wireName), `MCP wire name must be provider-safe: ${wireName}`)
  const parsed = parseMcpQualifiedName(wireName)
  assert(parsed?.server === server && parsed.tool === tool, `MCP name must round-trip: ${wireName}`)
}

for (const malformed of [
  'mcp____tool',
  'mcp__server__',
  'mcp__server',
  'mcp__server___tool',
  'mcp__server__tool_',
  'mcp__server__tool_zz',
  'mcp__server__tool_2',
  'mcp__server__tool.dot',
]) {
  assert(parseMcpQualifiedName(malformed) === null, `malformed MCP name must be rejected: ${malformed}`)
}

for (const [server, tool] of [
  ['', 'tool'],
  ['server', ''],
] as const) {
  let rejected = false
  try {
    mcpQualifiedName(server, tool)
  } catch {
    rejected = true
  }
  assert(rejected, 'empty MCP components must be rejected')
}

console.log('shared tool names self-check: ok')
