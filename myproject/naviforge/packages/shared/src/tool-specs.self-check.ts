import assert from 'node:assert/strict'

import { AGENT_TOOL_IDS } from './agent-tools.js'
import { formatToolApiDescription, getToolSpec, TOOL_SPEC_META, TOOL_SPECS } from './tool-specs.js'
import { builtinToolsForApi } from './openai-tools.js'

assert.equal(TOOL_SPECS.length, AGENT_TOOL_IDS.length)
for (const id of AGENT_TOOL_IDS) {
  assert.ok(TOOL_SPEC_META[id], `meta for ${id}`)
  const spec = getToolSpec(id)
  assert.equal(spec.id, id)
  assert.match(formatToolApiDescription(id), /\[risk=/)
}

const tools = builtinToolsForApi()
assert.equal(tools.length, AGENT_TOOL_IDS.length)
assert.ok(tools.some((tool) => tool.function.description.includes('risk=mutating') || tool.function.description.includes('risk=mixed')))
assert.ok(tools.find((tool) => tool.function.name === 'browser_act')?.function.description.includes('readonly-aux'))

console.log('tool-specs.self-check ok')
