import { chatCompletion, type LlmConfig } from '@naviforge/runtime'
import type { TraceRecord, ThreadMemory } from '@naviforge/session'
import { compactThreadMemoryWithLlm, formatThreadMemory, shouldCompactThread } from '@naviforge/session'

import type { AgentThread } from './thread-model'

export { shouldCompactThread }

export async function compactThreadMemory(
  thread: AgentThread,
  records: TraceRecord[],
  llm: LlmConfig
): Promise<ThreadMemory> {
  return compactThreadMemoryWithLlm(thread, records, async (system, user) => {
    const raw = await chatCompletion(llm, system, user)
    return raw.content
  })
}

export async function compactThreadSummary(
  thread: AgentThread,
  records: TraceRecord[],
  llm: LlmConfig
): Promise<string> {
  const memory = await compactThreadMemory(thread, records, llm)
  return formatThreadMemory(memory)
}
