import type { DomPlane, DomSnapshot, SnapshotMode } from '@naviforge/dom-plane'
import type { NetworkPlane } from '@naviforge/network-plane'
import type { ToolResult } from '@naviforge/shared'

import type { BuiltinContext } from './types.js'
import { num, str } from './types.js'

export function normalizeScrollArgs(
  args: Record<string, unknown>
): { to?: 'top' | 'bottom' | 'y'; y?: number; direction?: 'up' | 'down'; amount?: number } {
  const toRaw = str(args.to)
  const y = num(args.y)
  const direction = str(args.direction)
  const amount = num(args.amount)
  if (toRaw === 'top' || toRaw === 'bottom') return { to: toRaw }
  if (toRaw === 'y' && y != null) return { to: 'y', y }
  if (y != null) return { y }
  if (direction === 'up' || direction === 'down') return { direction, amount: amount ?? undefined }
  return { direction: 'down' }
}

export function parseSnapshotMode(value: unknown): SnapshotMode | undefined {
  return value === 'compact' || value === 'viewport' || value === 'full' ? value : undefined
}

export async function withStaleRevisionRetry<T>(
  dom: DomPlane,
  snap: DomSnapshot,
  run: (revision: number) => Promise<ToolResult<T>>
): Promise<{ result: ToolResult<T>; snap: DomSnapshot }> {
  let current = snap
  let result = await run(current.revision)
  if (!result.ok && result.error.code === 'stale_revision') {
    const fresh = await dom.snapshot()
    if (fresh.ok) {
      current = fresh.data
      result = await run(current.revision)
    }
  }
  return { result, snap: current }
}

export async function networkAfter(network: NetworkPlane | undefined, after: number) {
  if (!network) return undefined
  await new Promise((resolve) => setTimeout(resolve, 250))
  const events = await network.list({ limit: 10 })
  if (!events.ok) return undefined
  return [...events.data].reverse().find((event) => event.ts >= after && event.status != null)
}

export function handlerPrelude(input: BuiltinContext) {
  const { decision: turn, action, ctx, blockAsk } = input
  const {
    planes: { dom, network, tabs, scripts },
    taskScope,
    callMcpTool,
    mcpTools,
    allowDomInject,
    allowNetworkIntercept,
    skills,
  } = ctx
  return {
    turn,
    action,
    ctx,
    blockAsk,
    dom,
    network,
    tabs,
    scripts,
    taskScope,
    callMcpTool,
    mcpTools,
    allowDomInject,
    allowNetworkIntercept,
    skills,
    search: ctx.planes.search,
    fetch: ctx.planes.fetch,
    workspace: ctx.planes.workspace,
  }
}
