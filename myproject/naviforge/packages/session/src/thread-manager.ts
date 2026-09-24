import type { Thread, ThreadMemory } from './types.js'

export type ThreadManager = {
  listThreads(): Promise<Thread[]>
  createThread(title: string): Promise<Thread>
  updateThreadTitle(id: string, title: string): Promise<void>
  updateThreadMemory(id: string, memory: ThreadMemory, memoryAt?: number): Promise<void>
  updateThreadPlaybook(threadId: string, playbookId: string): Promise<void>
  touchThread(id: string): Promise<void>
}
