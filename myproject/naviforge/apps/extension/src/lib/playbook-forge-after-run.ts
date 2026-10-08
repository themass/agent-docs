import type { RecordedDomAction } from '@naviforge/playbook'
import { hostFromUrl } from '@naviforge/runtime'

import { forgeAndSave } from './playbook-store'
import { getSession, linkSessionPlaybook, updateThreadPlaybook } from './session-store'

export async function forgePlaybookAfterSuccessfulRun(opts: {
  task: string
  recordedActions: RecordedDomAction[]
  sessionId?: string
  pageUrl?: string
}): Promise<{ id: string; steps: number } | null> {
  const domActions = opts.recordedActions.filter(
    (action) => action.tool === 'dom_click' || action.tool === 'dom_type'
  )
  if (!domActions.length) return null

  const host = opts.pageUrl ? hostFromUrl(opts.pageUrl) : undefined
  const title = host ? `${host} · workflow` : opts.task.trim().slice(0, 72) || 'Agent workflow'

  const pb = await forgeAndSave({
    title,
    task: opts.task,
    host,
    actions: domActions,
  })
  if (!pb) return null

  let threadId: string | undefined
  if (opts.sessionId) {
    const session = await getSession(opts.sessionId)
    threadId = session?.threadId
    await linkSessionPlaybook(opts.sessionId, pb.id)
  }
  if (threadId) await updateThreadPlaybook(threadId, pb.id)

  return { id: pb.id, steps: pb.steps.length }
}
