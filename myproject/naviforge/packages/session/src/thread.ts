import { EMPTY_THREAD_MEMORY } from './thread-memory.js'
import type { Thread } from './types.js'

export function createThread(title: string): Thread {
  const now = Date.now()
  return {
    id: crypto.randomUUID(),
    title: title.trim().slice(0, 80) || 'Untitled thread',
    memory: { ...EMPTY_THREAD_MEMORY },
    createdAt: now,
    updatedAt: now,
  }
}
