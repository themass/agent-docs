/** Cursor-compatible `mcp/servers.json`: `{ "mcpServers": { "<name>": { command|url, ... } } }`. */

export type McpIssue = {
  level: 'error' | 'warning'
  server?: string
  message: string
  hint: string
}

export type McpTransport = 'stdio' | 'sse' | 'streamable-http'

export type NormalizedMcpServer = {
  id: string
  name: string
  transport: McpTransport
  command?: string
  args?: string[]
  env?: Record<string, string>
  envFile?: string
  cwd?: string
  endpoint?: string
  headers?: Record<string, string>
  enabled: boolean
  allowedTools: string[]
  extra?: Record<string, unknown>
}

export type McpDiscoveredTool = {
  name: string
  description?: string
  inputSchema?: unknown
}

export type McpDiscoveredResource = {
  uri: string
  name?: string
  description?: string
  mimeType?: string
}

export type McpDiscoveredPrompt = {
  name: string
  description?: string
  arguments?: unknown
}

/** Chrome storage / Host runtime overlay on the disk contract. */
export type McpConnection = NormalizedMcpServer & {
  discoveredTools?: McpDiscoveredTool[]
  discoveredResources?: McpDiscoveredResource[]
  discoveredPrompts?: McpDiscoveredPrompt[]
  checkedAt?: number
}

export type McpFileFormat = 'cursor' | 'legacy-connections' | 'legacy-array' | 'empty' | 'invalid'

export type ParseMcpResult = {
  servers: NormalizedMcpServer[]
  issues: McpIssue[]
  format: McpFileFormat
}

export type InterpolateCtx = {
  env: Record<string, string | undefined>
  userHome: string
  workspaceFolder: string
  pathSeparator: string
}

const KNOWN = new Set([
  'command',
  'args',
  'env',
  'envFile',
  'cwd',
  'url',
  'headers',
  'type',
  'disabled',
  'enabled',
  'allowedTools',
  'endpoint',
  'transport',
  'id',
  'name',
  'discoveredTools',
  'checkedAt',
])

export function mcpHasErrors(issues: McpIssue[]): boolean {
  return issues.some((issue) => issue.level === 'error')
}

function note(
  level: McpIssue['level'],
  message: string,
  hint: string,
  server?: string
): McpIssue {
  return server ? { level, message, hint, server } : { level, message, hint }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function stringMap(
  value: unknown,
  server: string,
  field: string,
  issues: McpIssue[]
): Record<string, string> | undefined {
  if (value === undefined) return undefined
  if (!isPlainObject(value)) {
    issues.push(
      note('error', `${field} 必须是字符串对象`, `写成 "${field}": { "KEY": "value" }`, server)
    )
    return undefined
  }
  const out: Record<string, string> = {}
  for (const [key, item] of Object.entries(value)) {
    if (typeof item !== 'string') {
      issues.push(
        note(
          'error',
          `${field}.${key} 必须是字符串`,
          'Cursor 的 env / headers 值只能是 string',
          server
        )
      )
      continue
    }
    out[key] = item
  }
  return out
}

function stringList(
  value: unknown,
  server: string,
  field: string,
  issues: McpIssue[]
): string[] | undefined {
  if (value === undefined) return undefined
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    issues.push(
      note('error', `${field} 必须是字符串数组`, `例如 "args": ["-y", "@scope/pkg"]`, server)
    )
    return undefined
  }
  return value
}

function readType(value: unknown): McpTransport | 'unknown' | undefined {
  if (value === undefined) return undefined
  if (typeof value !== 'string') return 'unknown'
  const type = value.toLowerCase().replace(/_/g, '-')
  if (type === 'stdio') return 'stdio'
  if (type === 'sse') return 'sse'
  if (type === 'http' || type === 'streamable-http' || type === 'streamablehttp') {
    return 'streamable-http'
  }
  return 'unknown'
}

function inferTransport(
  command: string | undefined,
  url: string | undefined,
  type: McpTransport | undefined
): McpTransport | undefined {
  if (type) return type
  if (command) return 'stdio'
  if (url && /\/sse(\/|\?|$)/i.test(url)) return 'sse'
  if (url) return 'streamable-http'
  return undefined
}

function extraFrom(raw: Record<string, unknown>): Record<string, unknown> | undefined {
  const extra: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(raw)) {
    if (!KNOWN.has(key)) extra[key] = value
  }
  return Object.keys(extra).length ? extra : undefined
}

function warnPlaceholders(server: string, fields: Array<string | undefined>, issues: McpIssue[]): void {
  for (const field of fields) {
    if (!field) continue
    const found = field.match(/\$\{[^}]+\}/g)
    if (!found) continue
    issues.push(
      note(
        'warning',
        `含占位符 ${found.join(', ')}`,
        '本机助手连接时展开 ${env:NAME}、${userHome}、${workspaceFolder}、${workspaceFolderBasename}、${pathSeparator}。未设置的环境变量会变成空字符串。',
        server
      )
    )
  }
}

function parseCursorServer(
  key: string,
  raw: unknown,
  issues: McpIssue[],
  defaultAllowAll: boolean
): NormalizedMcpServer | null {
  if (!isPlainObject(raw)) {
    issues.push(
      note(
        'error',
        '服务器配置必须是对象',
        '写成 { "command": "npx", "args": ["-y", "pkg"] } 或 { "url": "http://127.0.0.1:3000/mcp" }',
        key
      )
    )
    return null
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(key)) {
    issues.push(
      note(
        'warning',
        '服务器名建议只用字母、数字、点、下划线和短横线',
        'mcpServers 的 key 就是 Cursor 里的服务器名',
        key
      )
    )
  }
  if (raw.command !== undefined && typeof raw.command !== 'string') {
    issues.push(note('error', 'command 必须是字符串', '例如 "command": "npx"', key))
  }
  if (raw.url !== undefined && typeof raw.url !== 'string') {
    issues.push(note('error', 'url 必须是字符串', '远程 MCP 用 "url"，不要写成 endpoint', key))
  }
  if (raw.envFile !== undefined && typeof raw.envFile !== 'string') {
    issues.push(note('error', 'envFile 必须是字符串路径', 'envFile 只适用于 stdio', key))
  }
  if (raw.cwd !== undefined && typeof raw.cwd !== 'string') {
    issues.push(note('error', 'cwd 必须是字符串路径', '工作目录只适用于 stdio', key))
  }

  const command = typeof raw.command === 'string' ? raw.command.trim() : undefined
  const url = typeof raw.url === 'string' ? raw.url.trim() : undefined
  const envFile = typeof raw.envFile === 'string' ? raw.envFile : undefined
  const cwd = typeof raw.cwd === 'string' ? raw.cwd : undefined
  const args = stringList(raw.args, key, 'args', issues)
  const env = stringMap(raw.env, key, 'env', issues)
  const headers = stringMap(raw.headers, key, 'headers', issues)
  const type = readType(raw.type)
  if (type === 'unknown') {
    issues.push(note('error', `不支持的 type: ${String(raw.type)}`, '用 stdio、sse 或 http', key))
  }
  const typed = type === 'unknown' ? undefined : type
  if (command && url) {
    issues.push(
      note(
        'error',
        '不要同时写 command 和 url',
        '本地进程用 command + args；远程用 url（可加 headers）',
        key
      )
    )
  }
  const transport = inferTransport(command, url, typed)
  if (!transport) {
    issues.push(
      note(
        'error',
        '缺少 command 或 url',
        'stdio：{ "command": "npx", "args": ["-y", "pkg"] }；远程：{ "url": "https://host/mcp" }',
        key
      )
    )
    return null
  }
  if (typed && typed !== transport && command && typed !== 'stdio') {
    issues.push(note('error', `type 与 command 不匹配`, '有 command 时应为 "stdio"', key))
  }
  if (transport === 'stdio') {
    if (!command) {
      issues.push(note('error', 'stdio 需要 command', '填写可执行文件，例如 npx 或 uvx', key))
      return null
    }
    if (headers && Object.keys(headers).length) {
      issues.push(note('warning', 'stdio 会忽略 headers', '进程环境变量请写在 env 里', key))
    }
    if (
      /(^|[/\\])npx([.]cmd)?$/i.test(command) &&
      args &&
      args.length > 0 &&
      !args.includes('-y')
    ) {
      issues.push(
        note(
          'warning',
          'npx 建议带 -y',
          '写成 "args": ["-y", "包名"]，避免首次安装时卡住等确认',
          key
        )
      )
    }
  } else {
    if (!url) {
      issues.push(note('error', `${transport} 需要 url`, 'Cursor 远程字段名是 url，不是 endpoint', key))
      return null
    }
    if (envFile) issues.push(note('error', '远程 MCP 不能使用 envFile', '改用 headers', key))
    if (env && Object.keys(env).length) {
      issues.push(note('warning', '远程 MCP 会忽略 env', '鉴权写在 headers，例如 Authorization', key))
    }
    if (!url.includes('${')) {
      try {
        const parsed = new URL(url)
        if (!['http:', 'https:'].includes(parsed.protocol)) {
          issues.push(note('error', 'url 必须是 http(s)', '例如 http://127.0.0.1:3000/mcp', key))
        } else if (
          parsed.protocol === 'http:' &&
          parsed.hostname !== '127.0.0.1' &&
          parsed.hostname !== 'localhost' &&
          parsed.hostname !== '::1'
        ) {
          issues.push(
            note('warning', '非本机远程建议使用 https', '公网明文 HTTP 容易泄露 headers 里的密钥', key)
          )
        }
      } catch {
        issues.push(note('error', 'url 不是合法地址', '检查协议、主机名和端口', key))
      }
    }
  }
  if (raw.auth !== undefined) {
    issues.push(
      note(
        'warning',
        'auth / OAuth 尚未接入',
        '请改用 headers（远程）或 env（stdio）传入密钥',
        key
      )
    )
  }
  warnPlaceholders(key, [command, url, envFile, cwd, ...(env ? Object.values(env) : []), ...(headers ? Object.values(headers) : [])], issues)

  let allowedTools: string[]
  if (raw.allowedTools === undefined) {
    allowedTools = defaultAllowAll ? ['*'] : []
  } else {
    allowedTools = stringList(raw.allowedTools, key, 'allowedTools', issues) ?? []
  }
  const enabled = raw.disabled === true || raw.enabled === false ? false : true
  return {
    id: key,
    name: key,
    transport,
    command: transport === 'stdio' ? command : undefined,
    args: transport === 'stdio' ? args : undefined,
    env: transport === 'stdio' ? env : undefined,
    envFile: transport === 'stdio' ? envFile : undefined,
    cwd: transport === 'stdio' ? cwd : undefined,
    endpoint: transport === 'stdio' ? undefined : url,
    headers: transport === 'stdio' ? undefined : headers,
    enabled,
    allowedTools,
    extra: extraFrom(raw),
  }
}

function parseLegacyConnection(raw: unknown, issues: McpIssue[], index: number): NormalizedMcpServer | null {
  if (!isPlainObject(raw)) {
    issues.push(note('error', `connections[${index}] 必须是对象`, '旧格式是 { id, name, transport, command|endpoint }'))
    return null
  }
  const id = typeof raw.id === 'string' && raw.id.trim() ? raw.id.trim() : `server-${index + 1}`
  const name = typeof raw.name === 'string' && raw.name.trim() ? raw.name.trim() : id
  const asCursor: Record<string, unknown> = {
    ...raw,
    command: raw.command,
    url: typeof raw.url === 'string' ? raw.url : raw.endpoint,
    type: raw.type ?? raw.transport,
    disabled: raw.enabled === false,
  }
  const parsed = parseCursorServer(id, asCursor, issues, false)
  if (!parsed) return null
  return { ...parsed, name }
}

function parseDocument(value: unknown): ParseMcpResult {
  if (Array.isArray(value)) {
    const issues: McpIssue[] = [
      note(
        'warning',
        '正在把旧的数组格式改成 Cursor 的 mcpServers',
        '保存后会写成 { "mcpServers": { ... } }'
      ),
    ]
    const servers = value
      .map((item, index) => parseLegacyConnection(item, issues, index))
      .filter((item): item is NormalizedMcpServer => Boolean(item))
    return { servers, issues, format: 'legacy-array' }
  }
  if (!isPlainObject(value)) {
    return {
      servers: [],
      issues: [
        note('error', '根节点必须是对象', 'Cursor 格式：{ "mcpServers": { "name": { "command": "npx" } } }'),
      ],
      format: 'invalid',
    }
  }
  if (value.mcpServers !== undefined) {
    if (!isPlainObject(value.mcpServers)) {
      return {
        servers: [],
        issues: [
          note('error', 'mcpServers 必须是对象（不是数组）', 'key 是服务器名，value 是 command 或 url 配置'),
        ],
        format: 'invalid',
      }
    }
    const issues: McpIssue[] = []
    const servers: NormalizedMcpServer[] = []
    for (const [key, item] of Object.entries(value.mcpServers)) {
      const parsed = parseCursorServer(key, item, issues, true)
      if (parsed) servers.push(parsed)
    }
    if (!servers.length && !issues.length) {
      issues.push(
        note('warning', 'mcpServers 是空对象', '添加一个服务器，或从 Cursor 的 mcp.json 复制过来')
      )
    }
    return { servers, issues, format: 'cursor' }
  }
  if (Array.isArray(value.connections)) {
    const issues: McpIssue[] = [
      note(
        'warning',
        '正在把旧的 connections 列表改成 Cursor 的 mcpServers',
        '保存后会写成 { "mcpServers": { ... } }，可与 Cursor mcp.json 互换'
      ),
    ]
    const servers = value.connections
      .map((item, index) => parseLegacyConnection(item, issues, index))
      .filter((item): item is NormalizedMcpServer => Boolean(item))
    return { servers, issues, format: 'legacy-connections' }
  }
  return {
    servers: [],
    issues: [
      note(
        'error',
        '缺少 mcpServers',
        '和 Cursor 一样，根对象应是 { "mcpServers": { "fetch": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"] } } }'
      ),
    ],
    format: 'invalid',
  }
}

export function parseMcpServersJson(text: string): ParseMcpResult {
  const trimmed = text.trim()
  if (!trimmed) {
    return {
      servers: [],
      issues: [
        note(
          'warning',
          'mcp/servers.json 为空',
          '粘贴 Cursor 的 mcp.json：{ "mcpServers": { "name": { "command": "npx", "args": ["-y", "pkg"] } } }'
        ),
      ],
      format: 'empty',
    }
  }
  try {
    return parseDocument(JSON.parse(trimmed) as unknown)
  } catch (error) {
    return {
      servers: [],
      issues: [
        note(
          'error',
          'JSON 无法解析',
          `必须是严格 JSON（不能有注释或尾逗号）。${(error as Error).message}`
        ),
      ],
      format: 'invalid',
    }
  }
}

export function serializeMcpServersJson(servers: NormalizedMcpServer[]): string {
  const mcpServers: Record<string, Record<string, unknown>> = {}
  for (const server of servers) {
    const entry: Record<string, unknown> = { ...(server.extra ?? {}) }
    if (server.transport === 'stdio') {
      if (server.command) entry.command = server.command
      if (server.args?.length) entry.args = server.args
      if (server.env && Object.keys(server.env).length) entry.env = server.env
      if (server.envFile) entry.envFile = server.envFile
      if (server.cwd) entry.cwd = server.cwd
      delete entry.url
      delete entry.type
      delete entry.headers
    } else {
      if (server.endpoint) entry.url = server.endpoint
      entry.type = server.transport === 'sse' ? 'sse' : 'http'
      if (server.headers && Object.keys(server.headers).length) entry.headers = server.headers
      delete entry.command
      delete entry.args
      delete entry.env
      delete entry.envFile
      delete entry.cwd
    }
    if (!server.enabled) entry.disabled = true
    else delete entry.disabled
    if (server.allowedTools.length === 1 && server.allowedTools[0] === '*') delete entry.allowedTools
    else entry.allowedTools = server.allowedTools
    mcpServers[server.id] = entry
  }
  return `${JSON.stringify({ mcpServers }, null, 2)}\n`
}

/** Pretty-print MCP JSON; canonicalize to Cursor mcpServers when valid. */
export function formatMcpJsonText(text: string): { text: string; issues: McpIssue[]; changed: boolean } {
  const trimmed = text.trim()
  if (!trimmed) {
    const empty = serializeMcpServersJson([])
    return { text: empty, issues: parseMcpServersJson('').issues, changed: true }
  }
  try {
    const value = JSON.parse(trimmed) as unknown
    const parsed = parseDocument(value)
    const formatted =
      !mcpHasErrors(parsed.issues) || parsed.servers.length > 0
        ? serializeMcpServersJson(parsed.servers)
        : `${JSON.stringify(value, null, 2)}\n`
    return {
      text: formatted,
      issues: parsed.issues,
      changed: formatted !== text && formatted !== `${text}\n`,
    }
  } catch (error) {
    return {
      text,
      issues: [
        note(
          'error',
          'JSON 无法解析',
          `必须是严格 JSON（不能有注释或尾逗号）。${(error as Error).message}`
        ),
      ],
      changed: false,
    }
  }
}

export function prettyJson(value: unknown, maxLen = 12_000): string {
  const raw = JSON.stringify(value, null, 2)
  if (raw.length <= maxLen) return raw
  return `${raw.slice(0, maxLen)}\n… (truncated)`
}

export function interpolateMcpString(value: string, ctx: InterpolateCtx): string {
  const basename = ctx.workspaceFolder.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? ''
  return value
    .replaceAll('${userHome}', ctx.userHome)
    .replaceAll('${workspaceFolder}', ctx.workspaceFolder)
    .replaceAll('${workspaceFolderBasename}', basename)
    .replaceAll('${pathSeparator}', ctx.pathSeparator)
    .replaceAll('${/}', ctx.pathSeparator)
    .replace(/\$\{env:([A-Za-z_][A-Za-z0-9_]*)\}/g, (_all, name: string) => ctx.env[name] ?? '')
}

export function interpolateMcpRecord(
  record: Record<string, string> | undefined,
  ctx: InterpolateCtx
): Record<string, string> | undefined {
  if (!record) return undefined
  return Object.fromEntries(
    Object.entries(record).map(([key, value]) => [key, interpolateMcpString(value, ctx)])
  )
}
