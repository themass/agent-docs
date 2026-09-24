import assert from 'node:assert/strict'

import {
  formatMcpJsonText,
  interpolateMcpString,
  mcpHasErrors,
  parseMcpServersJson,
  serializeMcpServersJson,
} from './mcp-servers-json.js'

const cursor = parseMcpServersJson(`{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"],
      "env": { "FOO": "bar" }
    },
    "remote": {
      "url": "http://127.0.0.1:3000/mcp",
      "headers": { "Authorization": "Bearer t" }
    }
  }
}`)
assert.equal(cursor.format, 'cursor')
assert.equal(cursor.servers.length, 2)
assert.equal(cursor.servers[0]?.transport, 'stdio')
assert.deepEqual(cursor.servers[0]?.allowedTools, ['*'])
assert.equal(cursor.servers[0]?.env?.FOO, 'bar')
assert.equal(cursor.servers[1]?.transport, 'streamable-http')
assert.equal(cursor.servers[1]?.headers?.Authorization, 'Bearer t')
assert.equal(mcpHasErrors(cursor.issues), false)

const sse = parseMcpServersJson(`{"mcpServers":{"s":{"type":"sse","url":"https://example.com/sse"}}}`)
assert.equal(sse.servers[0]?.transport, 'sse')

const both = parseMcpServersJson(`{"mcpServers":{"x":{"command":"npx","url":"http://127.0.0.1/mcp"}}}`)
assert.equal(mcpHasErrors(both.issues), true)
assert.ok(both.issues.some((issue) => issue.message.includes('不要同时写')))

const missing = parseMcpServersJson(`{"servers":{}}`)
assert.equal(missing.format, 'invalid')
assert.ok(missing.issues.some((issue) => issue.message.includes('缺少 mcpServers')))

const legacy = parseMcpServersJson(`{"connections":[{"id":"fetch","name":"Fetch","transport":"stdio","command":"npx","args":["-y","pkg"],"enabled":true,"allowedTools":[]}]}`)
assert.equal(legacy.format, 'legacy-connections')
assert.deepEqual(legacy.servers[0]?.allowedTools, [])
assert.ok(legacy.issues.some((issue) => issue.level === 'warning'))

const roundtrip = parseMcpServersJson(serializeMcpServersJson(cursor.servers))
assert.equal(roundtrip.servers[0]?.command, 'npx')
assert.equal(roundtrip.servers[0]?.env?.FOO, 'bar')
assert.equal(roundtrip.servers[1]?.endpoint, 'http://127.0.0.1:3000/mcp')

const npx = parseMcpServersJson(`{"mcpServers":{"f":{"command":"npx","args":["@modelcontextprotocol/server-fetch"]}}}`)
assert.ok(npx.issues.some((issue) => issue.message.includes('npx 建议带 -y')))

const remoteHttp = parseMcpServersJson(`{"mcpServers":{"r":{"url":"http://example.com/mcp"}}}`)
assert.ok(remoteHttp.issues.some((issue) => issue.message.includes('https')))

const envFileRemote = parseMcpServersJson(`{"mcpServers":{"r":{"url":"http://127.0.0.1/mcp","envFile":".env"}}}`)
assert.ok(envFileRemote.issues.some((issue) => issue.level === 'error' && issue.message.includes('envFile')))

const disabled = parseMcpServersJson(`{"mcpServers":{"f":{"command":"npx","disabled":true}}}`)
assert.equal(disabled.servers[0]?.enabled, false)

const broken = parseMcpServersJson(`{mcpServers:}`)
assert.equal(broken.format, 'invalid')
assert.ok(broken.issues[0]?.hint.includes('严格 JSON'))

const expanded = interpolateMcpString('${userHome}${pathSeparator}${env:TOKEN}', {
  env: { TOKEN: 'abc' },
  userHome: '/Users/me',
  workspaceFolder: '/Users/me/NaviForge',
  pathSeparator: '/',
})
assert.equal(expanded, '/Users/me/abc')

const extras = parseMcpServersJson(`{"mcpServers":{"f":{"command":"uvx","auth":{"CLIENT_ID":"x"}}}}`)
assert.ok(extras.issues.some((issue) => issue.message.includes('OAuth')))
assert.equal((extras.servers[0]?.extra as { auth?: { CLIENT_ID: string } } | undefined)?.auth?.CLIENT_ID, 'x')
const again = parseMcpServersJson(serializeMcpServersJson(extras.servers))
assert.equal((again.servers[0]?.extra as { auth?: { CLIENT_ID: string } } | undefined)?.auth?.CLIENT_ID, 'x')

const minified = formatMcpJsonText('{"mcpServers":{"f":{"command":"npx","args":["-y","pkg"]}}}')
assert.ok(minified.changed, 'format expands minified JSON')
assert.ok(minified.text.includes('\n'), 'format pretty-prints')

console.log('mcp-servers-json self-check ok')
