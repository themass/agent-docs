#!/usr/bin/env node
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { McpServer } from '@modelcontextprotocol/server'
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio'
import * as z from 'zod/v4'

import {
  callAllowedTool,
  discoverConnection,
  listAllowedTools,
  setConnections,
  setMcpWorkspace,
} from './mcp-client.js'
import { runSystemTraceroute } from './traceroute.js'
import {
  defaultWorkspaceRoot,
  dispatchWorkspace,
  ensureWorkspace,
  readMcp,
  resolveHostToken,
} from './workspace.js'

const VERSION = '0.0.1'
const PORT = Number(process.env.NAVIFORGE_HOST_PORT ?? 17373)
const MAX_BODY_BYTES = 16_000_000
const HTTP_ONLY =
  process.env.NAVIFORGE_HOST_HTTP_ONLY === '1' || process.env.NAVIFORGE_HOST_HTTP_ONLY === 'true'

type TaskResult = {
  ok: boolean
  status: string
  result?: string
  error?: string
}

type BrowserTask = {
  id: string
  instruction: string
  tabId?: number
  useNetwork: boolean
  createdAt: number
  claimed: boolean
  resolve: (result: TaskResult) => void
}

const tasks = new Map<string, BrowserTask>()
const ConnectionSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  transport: z.enum(['streamable-http', 'sse', 'stdio']),
  endpoint: z.string().optional(),
  command: z.string().optional(),
  args: z.array(z.string()).optional(),
  env: z.record(z.string(), z.string()).optional(),
  envFile: z.string().optional(),
  cwd: z.string().optional(),
  headers: z.record(z.string(), z.string()).optional(),
  enabled: z.boolean(),
  allowedTools: z.array(z.string()),
})

let TOKEN = ''
let workspaceRoot = defaultWorkspaceRoot()

async function reloadMcpFromDisk(): Promise<void> {
  setMcpWorkspace(workspaceRoot)
  const { connections, issues } = await readMcp(workspaceRoot)
  for (const issue of issues) {
    const where = issue.server ? ` ${issue.server}` : ''
    console.error(`MCP ${issue.level}${where}: ${issue.message}`)
  }
  await setConnections(connections)
}

function mcpDiskTouched(rec: Record<string, unknown>): boolean {
  if (rec.op === 'writeMcp' || rec.op === 'writeMcpText') return true
  if (rec.op === 'write' && String(rec.path ?? '').replace(/\\/g, '/') === 'mcp/servers.json') {
    return true
  }
  return false
}

function json(response: ServerResponse, status: number, value: unknown): void {
  response.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS, PUT',
  })
  response.end(JSON.stringify(value))
}

function isLoopback(request: IncomingMessage): boolean {
  const ip = request.socket.remoteAddress ?? ''
  return ip === '127.0.0.1' || ip === '::1' || ip === '::ffff:127.0.0.1'
}

function authorized(request: IncomingMessage): boolean {
  return Boolean(TOKEN) && request.headers.authorization === `Bearer ${TOKEN}`
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of request) {
    const buffer = Buffer.from(chunk)
    size += buffer.length
    if (size > MAX_BODY_BYTES) throw new Error('Request body exceeds 16 MB')
    chunks.push(buffer)
  }
  const raw = Buffer.concat(chunks).toString('utf8')
  if (!raw) return {}
  return JSON.parse(raw)
}

function createBridge(): ReturnType<typeof createServer> {
  return createServer(async (request, response) => {
    if (request.method === 'OPTIONS') {
      json(response, 204, null)
      return
    }

    const url = new URL(request.url ?? '/', `http://127.0.0.1:${PORT}`)
    const loopback = isLoopback(request)

    if (request.method === 'GET' && url.pathname === '/local/bootstrap') {
      if (!loopback) {
        json(response, 403, { error: 'bootstrap is local-only' })
        return
      }
      json(response, 200, {
        ok: true,
        url: `http://127.0.0.1:${PORT}`,
        token: TOKEN,
        workspaceRoot,
        version: VERSION,
      })
      return
    }

    if (request.method === 'GET' && url.pathname === '/health') {
      if (!loopback && !authorized(request)) {
        json(response, 401, { error: 'Invalid Host token' })
        return
      }
      json(response, 200, {
        ok: true,
        version: VERSION,
        pendingTasks: tasks.size,
        workspaceRoot,
      })
      return
    }

    if (!authorized(request)) {
      json(response, 401, { error: 'Invalid Host token' })
      return
    }

    if (request.method === 'POST' && url.pathname === '/workspace') {
      try {
        const body = await readJson(request)
        const rec = body && typeof body === 'object' ? (body as Record<string, unknown>) : {}
        if (rec.op === 'setRoot' && typeof rec.root === 'string' && rec.root.trim()) {
          workspaceRoot = rec.root.trim()
          await ensureWorkspace(workspaceRoot)
          await reloadMcpFromDisk()
          json(response, 200, { ok: true, root: workspaceRoot })
          return
        }
        const result = await dispatchWorkspace(workspaceRoot, body)
        if (mcpDiskTouched(rec)) await reloadMcpFromDisk()
        json(response, 200, result)
      } catch (error) {
        json(response, 400, { error: (error as Error).message })
      }
      return
    }

    if (request.method === 'POST' && url.pathname === '/mcp/connections') {
      try {
        const body = z
          .object({ connections: z.array(ConnectionSchema).max(50) })
          .strict()
          .parse(await readJson(request))
        await setConnections(body.connections)
        json(response, 200, { ok: true, count: body.connections.length })
      } catch (error) {
        json(response, 400, { error: (error as Error).message })
      }
      return
    }
    if (request.method === 'GET' && url.pathname === '/mcp/tools') {
      try {
        json(response, 200, { tools: await listAllowedTools() })
      } catch (error) {
        json(response, 502, { error: (error as Error).message })
      }
      return
    }
    if (request.method === 'POST' && url.pathname === '/mcp/discover') {
      try {
        const body = z
          .object({ connection: ConnectionSchema })
          .strict()
          .parse(await readJson(request))
        await setConnections([{ ...body.connection, enabled: true, allowedTools: ['*'] }])
        json(response, 200, await discoverConnection(body.connection))
      } catch (error) {
        json(response, 502, { error: (error as Error).message })
      }
      return
    }
    if (request.method === 'POST' && url.pathname === '/mcp/call') {
      try {
        const body = z
          .object({
            serverId: z.string().min(1),
            tool: z.string().min(1),
            arguments: z.record(z.string(), z.unknown()).default({}),
          })
          .strict()
          .parse(await readJson(request))
        json(response, 200, {
          result: await callAllowedTool(body.serverId, body.tool, body.arguments),
        })
      } catch (error) {
        json(response, 502, { error: (error as Error).message })
      }
      return
    }
    if (request.method === 'GET' && url.pathname === '/tasks/next') {
      const task = [...tasks.values()].find((candidate) => !candidate.claimed)
      if (!task) {
        response.writeHead(204, {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Headers': 'Authorization, Content-Type',
        })
        response.end()
        return
      }
      task.claimed = true
      json(response, 200, {
        id: task.id,
        instruction: task.instruction,
        tabId: task.tabId,
        useNetwork: task.useNetwork,
      })
      return
    }

    if (request.method === 'POST' && url.pathname === '/net/traceroute') {
      try {
        const body = z
          .object({
            target: z.string().min(1).max(253),
            maxHops: z.number().int().min(1).max(30).optional(),
          })
          .strict()
          .parse(await readJson(request))
        json(response, 200, await runSystemTraceroute(body.target, body.maxHops ?? 20))
      } catch (error) {
        json(response, 400, { error: (error as Error).message })
      }
      return
    }

    const match = url.pathname.match(/^\/tasks\/([^/]+)\/result$/)
    if (request.method === 'POST' && match) {
      const task = tasks.get(match[1])
      if (!task) {
        json(response, 404, { error: 'Task not found or expired' })
        return
      }
      try {
        const result = z
          .object({
            ok: z.boolean(),
            status: z.string(),
            result: z.string().optional(),
            error: z.string().optional(),
          })
          .strict()
          .parse(await readJson(request))
        tasks.delete(task.id)
        task.resolve(result)
        json(response, 200, { ok: true })
      } catch (error) {
        json(response, 400, { error: (error as Error).message })
      }
      return
    }

    json(response, 404, { error: 'Unknown Host endpoint' })
  })
}

async function queueBrowserTask(input: {
  instruction: string
  tabId?: number
  useNetwork: boolean
  timeoutSeconds: number
}): Promise<TaskResult> {
  return new Promise((resolve) => {
    const id = randomUUID()
    const timeout = setTimeout(() => {
      tasks.delete(id)
      resolve({
        ok: false,
        status: 'timeout',
        error: 'No extension result arrived. Enable the Host bridge in NaviForge Settings.',
      })
    }, input.timeoutSeconds * 1000)
    tasks.set(id, {
      id,
      instruction: input.instruction,
      tabId: input.tabId,
      useNetwork: input.useNetwork,
      createdAt: Date.now(),
      claimed: false,
      resolve: (result) => {
        clearTimeout(timeout)
        resolve(result)
      },
    })
  })
}

export async function startHttpServer(): Promise<void> {
  workspaceRoot = defaultWorkspaceRoot()
  await ensureWorkspace(workspaceRoot)
  TOKEN = await resolveHostToken(workspaceRoot, process.env.NAVIFORGE_HOST_TOKEN)
  await reloadMcpFromDisk()
  const bridge = createBridge()
  await new Promise<void>((resolve, reject) => {
    bridge.once('error', reject)
    bridge.listen(PORT, '127.0.0.1', resolve)
  })
  console.error(`NaviForge Host listening on http://127.0.0.1:${PORT}`)
  console.error(`Workspace ${workspaceRoot}`)
}

async function connectMcpStdio(): Promise<void> {
  const server = new McpServer({ name: 'naviforge-mcp-server', version: VERSION })
  server.registerTool(
    'naviforge_get_status',
    {
      title: 'Get NaviForge Host status',
      description: 'Check whether the local NaviForge Host is running and how many browser tasks are pending.',
      inputSchema: z.object({}).strict(),
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => ({
      content: [
        {
          type: 'text',
          text: JSON.stringify({ version: VERSION, bridgePort: PORT, pendingTasks: tasks.size, workspaceRoot }),
        },
      ],
    })
  )
  server.registerTool(
    'naviforge_execute_browser_task',
    {
      title: 'Execute browser task',
      description:
        'Ask the connected NaviForge Chrome extension to perform one browser task in the active tab. Use for DOM interaction and optional network observation. The user must enable the local Host bridge.',
      inputSchema: z
        .object({
          instruction: z.string().min(1).max(4000).describe('Clear browser task in natural language.'),
          tabId: z.number().int().positive().optional().describe('Chrome tab ID; omit to use the active tab.'),
          useNetwork: z.boolean().default(true).describe('Enable filtered Chrome DevTools network observation.'),
          timeoutSeconds: z.number().int().min(10).max(300).default(120),
        })
        .strict(),
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    async (input) => {
      const result = await queueBrowserTask(input)
      return {
        content: [{ type: 'text', text: JSON.stringify(result) }],
        isError: !result.ok,
      }
    }
  )

  await server.connect(new StdioServerTransport())
}

async function main(): Promise<void> {
  await startHttpServer()
  if (HTTP_ONLY) {
    console.error('HTTP-only mode (no MCP stdio on stdin)')
    return
  }
  await connectMcpStdio()
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])
if (isMain) {
  main().catch((error: unknown) => {
    console.error((error as Error).message)
    process.exitCode = 1
  })
}
