import type { QueuedTask } from '@naviforge/runtime'
import type { TraceRecord } from '@naviforge/session'

export type AgentRunMessage = {
  type: 'AGENT_RUN'
  action: 'status' | 'stop' | 'pause' | 'resume' | 'steer' | 'follow_up' | 'reply' | 'queue_list' | 'queue_set'
  text?: string
  id?: string
  tasks?: QueuedTask[]
}

export type AgentRunSnapshot = {
  active?: boolean
  status?: string
  tabId?: number
  events?: TraceRecord[]
  tasks?: QueuedTask[]
  pending?: { steering: number; followUp: number }
}

type Send = <T>(message: AgentRunMessage) => Promise<T>

export function createAgentRunController(send: Send) {
  return {
    status: (): Promise<AgentRunSnapshot> => send({ type: 'AGENT_RUN', action: 'status' }),
    pause: (): Promise<{ ok?: boolean }> => send({ type: 'AGENT_RUN', action: 'pause' }),
    resume: (): Promise<{ ok?: boolean }> => send({ type: 'AGENT_RUN', action: 'resume' }),
    stop: (): Promise<{ ok?: boolean }> => send({ type: 'AGENT_RUN', action: 'stop' }),
    steer: (text: string): Promise<{ ok?: boolean; asHitl?: boolean; pending?: { steering: number; followUp: number } }> =>
      send({ type: 'AGENT_RUN', action: 'steer', text }),
    followUp: (task: QueuedTask): Promise<{ ok?: boolean; pending?: { steering: number; followUp: number }; tasks?: QueuedTask[] }> =>
      send({ type: 'AGENT_RUN', action: 'follow_up', text: task.text, id: task.id }),
    reply: (text: string): Promise<{ ok?: boolean }> => send({ type: 'AGENT_RUN', action: 'reply', text }),
    queue: (): Promise<{ ok?: boolean; tasks?: QueuedTask[]; pending?: { steering: number; followUp: number } }> =>
      send({ type: 'AGENT_RUN', action: 'queue_list' }),
    replaceQueue: (tasks: QueuedTask[]): Promise<{ ok?: boolean; tasks?: QueuedTask[]; pending?: { steering: number; followUp: number } }> =>
      send({ type: 'AGENT_RUN', action: 'queue_set', tasks: cleanQueuedTasks(tasks) }),
  }
}

/** Never create or replace task IDs in the UI; background remains their authority. */
export function cleanQueuedTasks(tasks: QueuedTask[]): QueuedTask[] {
  return tasks
    .map((task) => ({ ...task, text: task.text.trim() }))
    .filter((task) => task.id && task.text)
}
