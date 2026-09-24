import { AGENT_TOOL_IDS, mcpQualifiedName } from '@naviforge/shared'

import { MCP_TOOL_CAP, exposeMcpTools, formatMcpToolCatalog, resolveMcpCall } from './mcp-tools.js'
import { ToolRegistry } from './tools/registry.js'

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

const registryModule = await import('./tools/builtin-handlers.js').catch(() => null)
assert(registryModule, 'builtin ToolRegistry module must exist')

const registry = registryModule.BUILTIN_TOOL_REGISTRY as {
  ids(): readonly string[]
  assertCatalog(catalogIds: readonly string[]): void
}
assert(registry, 'builtin ToolRegistry must be exported')
registry.assertCatalog(AGENT_TOOL_IDS)
assert(
  new Set(registry.ids()).size === registry.ids().length,
  'builtin ToolRegistry must not contain duplicate handlers'
)
assert(
  registry.ids().length >= AGENT_TOOL_IDS.length,
  'builtin ToolRegistry must cover every catalog builtin'
)
for (const id of AGENT_TOOL_IDS) {
  assert(registry.get(id), `builtin ToolRegistry missing handler: ${id}`)
}
assert(
  registry.get('workspace_ls') !== registry.get('workspace_read'),
  'workspace tools must register individual handlers'
)

const configured = [
  {
    serverId: 'a.b',
    serverName: 'Dot server',
    name: 'read_file',
    inputSchema: { type: 'object', properties: {} },
  },
]
const untrustedCollision = resolveMcpCall(
  mcpQualifiedName('a_b', 'read_file'),
  {},
  configured
)
assert(!untrustedCollision.ok, 'MCP authorization must match a listed raw server/tool pair')

const authorized = resolveMcpCall(mcpQualifiedName('a.b', 'read_file'), {}, configured)
assert(
  authorized.ok &&
    authorized.call.serverId === configured[0]?.serverId &&
    authorized.call.tool === configured[0]?.name,
  'MCP authorization must preserve configured raw names'
)

const capped = Array.from({ length: MCP_TOOL_CAP + 1 }, (_, index) => ({
  serverId: index === 0 ? 'docs.example' : 'docs',
  serverName: 'Docs',
  name: index === 0 ? 'search/tool' : `tool_${index}`,
  inputSchema: { type: 'object', properties: {} },
}))
const exposed = exposeMcpTools(capped)
assert(exposed.length === MCP_TOOL_CAP, 'MCP catalog must expose an explicit capped list')
assert(Object.isFrozen(exposed), 'MCP catalog must be frozen before model use')
const exposedExoticName = mcpQualifiedName('docs.example', 'search/tool')
assert(
  resolveMcpCall(exposedExoticName, {}, exposed).ok,
  'an exposed encoded MCP tool must remain invokable by its exact wire name'
)
const omittedName = mcpQualifiedName('docs', `tool_${MCP_TOOL_CAP}`)
assert(
  !resolveMcpCall(omittedName, {}, exposed).ok,
  'the omitted MCP tool beyond the cap must be denied'
)
const catalog = formatMcpToolCatalog(exposed) ?? ''
assert(catalog.includes(exposedExoticName), 'prompt catalog must use the exposed MCP list')
assert(!catalog.includes(omittedName), 'prompt catalog must omit tools beyond the cap')

for (const id of ['dom.click', 'Dom_click', 'mcp__spoof', '_dom_click', 'dom-click']) {
  let rejected = false
  try {
    new ToolRegistry<undefined, undefined>().register(id, () => undefined)
  } catch {
    rejected = true
  }
  assert(rejected, `tool registry must reject invalid builtin id: ${id}`)
}

console.log('runtime tool registry self-check: ok')
