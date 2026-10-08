import type { AgentCtx } from './agent-ctx.js'
import { isContinuationMessage } from '@naviforge/session'
import { lockDeliverable, resolveDeliverable } from './deliverable.js'

export function anchorTask(ctx: AgentCtx): string {
  const stored = ctx.metadata.anchorTask
  return typeof stored === 'string' && stored.trim() ? stored.trim() : ctx.task.trim()
}

export function ensureAnchorTask(ctx: AgentCtx): string {
  if (!ctx.metadata.anchorTask) {
    const task = ctx.task.trim()
    const hint =
      typeof ctx.agent.opts.taskAnchor === 'string' ? ctx.agent.opts.taskAnchor.trim() : ''
    ctx.metadata.anchorTask =
      isContinuationMessage(task) && hint ? hint : task
  }
  return anchorTask(ctx)
}

export function syncDeliverableFromTask(ctx: AgentCtx): void {
  const anchor = ensureAnchorTask(ctx)
  ctx.gates.deliverable = lockDeliverable(anchor, ctx.task)
}

export function taskTextForRouting(ctx: AgentCtx): string {
  return anchorTask(ctx)
}

/** Used by extension to decide network plane before run. */
export function taskRequiresNetworkPlane(task: string): boolean {
  const d = resolveDeliverable(task)
  return d === 'media' || d === 'script' || d === 'data'
}

/** OR across follow-up text + session anchor (e.g. user sends「继续」). */
export function shouldEnableNetworkPlane(...tasks: string[]): boolean {
  return tasks.some((t) => t.trim() && taskRequiresNetworkPlane(t))
}
