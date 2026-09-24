import type { LlmConfig } from '@naviforge/runtime'

import { listThreadRecords, listThreads, updateThreadMemory } from '../lib/session-store'
import type { AgentThread } from '../lib/thread-model'
import { threadSummaryFromMemory } from '../lib/thread-model'
import { compactThreadMemory, shouldCompactThread } from '../lib/thread-summary'
import { memoryPatchFromRun, mergeThreadMemory } from '@naviforge/session'

export type ThreadMemoryUpdate = {
  threadId: string
  task: string
  result: string
  mode?: string
  llm: LlmConfig
  /** When false, keep existing GOAL slot (e.g. follow-up「继续」). */
  setGoal?: boolean
}

/** Persist a cheap memory patch first; compression remains an optional best-effort upgrade. */
export async function persistThreadMemory(update: ThreadMemoryUpdate): Promise<AgentThread | null> {
  if (!update.result.trim()) return null
  const thread = (await listThreads()).find((item) => item.id === update.threadId)
  if (!thread) return null

  let memory = mergeThreadMemory(
    thread.memory,
    memoryPatchFromRun({
      task: update.task,
      result: update.result,
      mode: update.mode,
      setGoal: update.setGoal,
    })
  )
  if (shouldCompactThread(memory) && update.llm.apiKey.trim()) {
    try {
      memory = await compactThreadMemory({ ...thread, memory }, await listThreadRecords(update.threadId), update.llm)
    } catch {
      // A failed model call must not discard the durable cheap memory patch.
    }
  }

  await updateThreadMemory(update.threadId, memory)
  return { ...thread, memory, updatedAt: Date.now() }
}

export { threadSummaryFromMemory }
