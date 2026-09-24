import { homedir } from 'node:os'
import path from 'node:path'
import { readFile } from 'node:fs/promises'

import {
  Client,
  SSEClientTransport,
  StreamableHTTPClientTransport,
} from '@modelcontextprotocol/client'
import { getDefaultEnvironment, StdioClientTransport } from '@modelcontextprotocol/client/stdio'

import {
  interpolateMcpRecord,
  interpolateMcpString,
  type InterpolateCtx,
  type McpConnection,
} from '@naviforge/shared'

export type { McpConnection }

export type AvailableTool = {
  serverId: string
  serverName: string
  name: string
  description?: string
  inputSchema: unknown
}

export type McpDiscoveryResource = AvailableTool & {
  uri: string
  mimeType?: string
}

export type McpDiscoveryPrompt = {
  serverId: string
  serverName: string
  name: string
  description?: string
  arguments?: unknown
}

export type McpServerDiscovery = {
  serverId: string
  serverName: string
  tools: Array<{ name: string; description?: string; inputSchema?: unknown; qualifiedName: string }>
  resources: Array<{ uri: string; name?: string; description?: string; mimeType?: string }>
  prompts: Array<{ name: string; description?: string; arguments?: unknown }>
  error?: string
}

const connections = new Map<string, McpConnection>()
const clients = new Map<string, Client>()
let fingerprint = ''
let workspaceFolder = ''

export function setMcpWorkspace(root: string): void {
  workspaceFolder = root
}

function interpolateCtx(): InterpolateCtx {
  return {
    env: process.env,
    userHome: homedir(),
    workspaceFolder: workspaceFolder || homedir(),
    pathSeparator: path.sep,
  }
}

function parseDotEnv(text: string): Record<string, string> {
  const env: Record<string, string> = {}
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const eq = trimmed.indexOf('=')
    if (eq < 1) continue
    const key = trimmed.slice(0, eq).trim().replace(/^export\s+/, '')
    let value = trimmed.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    env[key] = value
  }
  return env
}

function isAllowed(connection: McpConnection, tool: string): boolean {
  return connection.allowedTools.includes('*') || connection.allowedTools.includes(tool)
}

async function closeClients(): Promise<void> {
  await Promise.allSettled([...clients.values()].map((client) => client.close()))
  clients.clear()
}

export async function setConnections(next: McpConnection[]): Promise<void> {
  const nextFingerprint = JSON.stringify(next)
  if (nextFingerprint === fingerprint) return
  await closeClients()
  connections.clear()
  for (const connection of next) connections.set(connection.id, connection)
  fingerprint = nextFingerprint
}

async function stdioEnv(connection: McpConnection, ctx: InterpolateCtx): Promise<Record<string, string>> {
  const merged = { ...getDefaultEnvironment() }
  if (connection.envFile) {
    const interpolated = interpolateMcpString(connection.envFile, ctx)
    const abs = path.isAbsolute(interpolated)
      ? interpolated
      : path.resolve(ctx.workspaceFolder, interpolated)
    try {
      Object.assign(merged, parseDotEnv(await readFile(abs, 'utf8')))
    } catch (error) {
      throw new Error(`MCP ${connection.name}: cannot read envFile ${abs}: ${(error as Error).message}`)
    }
  }
  Object.assign(merged, interpolateMcpRecord(connection.env, ctx) ?? {})
  return merged
}

function requestInit(headers: Record<string, string> | undefined): RequestInit | undefined {
  if (!headers || !Object.keys(headers).length) return undefined
  return { headers }
}

async function connect(connection: McpConnection): Promise<Client> {
  const existing = clients.get(connection.id)
  if (existing) return existing

  const ctx = interpolateCtx()
  const client = new Client({ name: 'naviforge-host', version: '0.0.1' })
  if (connection.transport === 'stdio') {
    if (!connection.command) throw new Error(`MCP ${connection.name}: command is required`)
    const command = interpolateMcpString(connection.command, ctx)
    const args = (connection.args ?? []).map((item) => interpolateMcpString(item, ctx))
    const cwd = connection.cwd ? interpolateMcpString(connection.cwd, ctx) : undefined
    await client.connect(
      new StdioClientTransport({
        command,
        args,
        env: await stdioEnv(connection, ctx),
        cwd,
      })
    )
  } else {
    if (!connection.endpoint) throw new Error(`MCP ${connection.name}: endpoint is required`)
    const url = new URL(interpolateMcpString(connection.endpoint, ctx))
    const headers = interpolateMcpRecord(connection.headers, ctx)
    const init = requestInit(headers)
    await client.connect(
      connection.transport === 'sse'
        ? new SSEClientTransport(url, init ? { requestInit: init } : undefined)
        : new StreamableHTTPClientTransport(url, init ? { requestInit: init } : undefined)
    )
  }
  clients.set(connection.id, client)
  return client
}

export async function listAllowedTools(): Promise<AvailableTool[]> {
  const result: AvailableTool[] = []
  for (const connection of connections.values()) {
    if (!connection.enabled || !connection.allowedTools.length) continue
    try {
      const client = await connect(connection)
      const { tools } = await client.listTools()
      for (const tool of tools) {
        if (!isAllowed(connection, tool.name)) continue
        result.push({
          serverId: connection.id,
          serverName: connection.name,
          name: tool.name,
          description: tool.description,
          inputSchema: tool.inputSchema,
        })
      }
    } catch (error) {
      console.error(`MCP ${connection.name} unavailable: ${(error as Error).message}`)
    }
  }
  return result
}

function qualifiedToolName(serverId: string, tool: string): string {
  return `mcp__${serverId}__${tool}`
}

/** Full MCP catalog for one connection (tools / resources / prompts). */
export async function discoverConnection(connection: McpConnection): Promise<McpServerDiscovery> {
  const base: McpServerDiscovery = {
    serverId: connection.id,
    serverName: connection.name,
    tools: [],
    resources: [],
    prompts: [],
  }
  try {
    const client = await connect({ ...connection, enabled: true, allowedTools: ['*'] })
    const { tools } = await client.listTools()
    base.tools = tools.map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema,
      qualifiedName: qualifiedToolName(connection.id, tool.name),
    }))
    try {
      const { resources } = await client.listResources()
      base.resources = resources.map((resource) => ({
        uri: resource.uri,
        name: resource.name,
        description: resource.description,
        mimeType: resource.mimeType,
      }))
    } catch {
      base.resources = []
    }
    try {
      const { prompts } = await client.listPrompts()
      base.prompts = prompts.map((prompt) => ({
        name: prompt.name,
        description: prompt.description,
        arguments: prompt.arguments,
      }))
    } catch {
      base.prompts = []
    }
    return base
  } catch (error) {
    return { ...base, error: (error as Error).message }
  }
}

export async function callAllowedTool(
  serverId: string,
  tool: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const connection = connections.get(serverId)
  if (!connection?.enabled) throw new Error(`MCP connection is disabled or missing: ${serverId}`)
  if (!isAllowed(connection, tool)) throw new Error(`MCP tool is not allowlisted: ${tool}`)
  const client = await connect(connection)
  return client.callTool({ name: tool, arguments: args })
}
