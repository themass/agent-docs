import type { MutableRefObject } from 'react'
import type { RunAgentResult } from '@naviforge/runtime'
import { RUN_STATUS, type WorkspaceRunStatus } from '../lib/run-phase'
import {
  createMessageQueue,
  createQueuedTask,
  type QueuedTask,
} from '@naviforge/runtime'

import { updateActivity } from '../lib/activity-store'
import type { AgentSession } from '../lib/session-model'
import { cleanQueuedTasks } from './agent-run-controller'
import type { WorkspaceRunOutcome } from './run-outcome'

export type QueueControlDeps = {
  queueRef: MutableRefObject<ReturnType<typeof createMessageQueue>>
  pendingTasksRef: MutableRefObject<QueuedTask[]>
  processLockRef: MutableRefObject<boolean>
  runningRef: MutableRefObject<boolean>
  currentTaskRef: MutableRefObject<QueuedTask | null>
  voiceRef: MutableRefObject<{ dataUrl: string; path?: string; label: string } | null>
  imageRef: MutableRefObject<{ dataUrl: string; label: string } | null>
  pendingVoiceByTaskRef: MutableRefObject<
    Map<string, { dataUrl: string; path?: string; label: string }>
  >
  pendingImageByTaskRef: MutableRefObject<
    Map<string, { dataUrl: string; label: string }>
  >
  activityRef: MutableRefObject<string | null>
  activeRunIdRef: MutableRefObject<string | null>
  sessionRef: MutableRefObject<string | null>
  markSessionComplete(
    sessionId: string,
    status: AgentSession['status'],
    result?: string
  ): Promise<void>
  task: string
  running: boolean
  status: string
  awaitingQuestion: string | null
  setTask(value: string | ((current: string) => string)): void
  setVoiceAttachment(value: { dataUrl: string; path?: string; label: string } | null): void
  setImageAttachment(value: { dataUrl: string; label: string } | null): void
  setPendingTasks(value: QueuedTask[]): void
  setQueuePending(value: { steering: number; followUp: number }): void
  setRunning(value: boolean): void
  setRunStartedAt(value: number | null): void
  setCurrentTask(value: QueuedTask | null): void
  setStatus(value: WorkspaceRunStatus): void
  setStatusDetail(value: string | null): void
  setLiveFeed(value: string[]): void
  setAwaitingQuestion(value: string | null): void
  setRunOutcome(value: WorkspaceRunOutcome | null): void
  push(line: string): void
  recordSession(record: { type: 'user.task'; payload: { text: string; audioPath?: string; audioLabel?: string } }): void
  appendLocal(
    type: 'user.task',
    payload: {
      text: string
      audioPath?: string
      audioLabel?: string
      audioDataUrl?: string
      imageDataUrl?: string
      imageLabel?: string
    }
  ): void
  agentRun: {
    followUp(item: QueuedTask): Promise<{ ok?: boolean; pending?: { steering: number; followUp: number }; tasks?: QueuedTask[] }>
    steer(text: string): Promise<{ ok?: boolean; asHitl?: boolean; pending?: { steering: number; followUp: number } }>
    reply(text: string): Promise<{ ok?: boolean }>
    replaceQueue(tasks: QueuedTask[]): Promise<{ pending?: { steering: number; followUp: number }; tasks?: QueuedTask[] }>
  }
  startRun(taskItem: QueuedTask): Promise<void>
}

export function createQueueControl(deps: QueueControlDeps) {
  function syncQueuePending(): void {
    deps.setQueuePending(deps.queueRef.current.pending())
  }

  function syncPendingTasks(tasks: QueuedTask[]): void {
    deps.pendingTasksRef.current = tasks
    deps.setPendingTasks(tasks)
  }

  async function refreshPendingTasks(): Promise<void> {
    try {
      const state = (await chrome.runtime.sendMessage({ type: 'AGENT_RUN', action: 'queue_list' })) as {
        ok?: boolean
        tasks?: QueuedTask[]
        pending?: { steering: number; followUp: number }
      }
      // No active run → keep local leftovers (do not wipe the UI queue).
      if (!deps.runningRef.current && state?.ok === false) return
      if (Array.isArray(state.tasks)) syncPendingTasks(state.tasks)
      if (state.pending) deps.setQueuePending(state.pending)
    } catch {
      /* ignore */
    }
  }

  function replacePendingTasks(tasks: QueuedTask[]): void {
    const cleaned = cleanQueuedTasks(tasks)
    syncPendingTasks(cleaned)
    if (!deps.runningRef.current) return
    void deps.agentRun
      .replaceQueue(cleaned)
      .then((r) => {
        if (r?.pending) deps.setQueuePending(r.pending)
        if (Array.isArray(r.tasks)) syncPendingTasks(r.tasks)
      })
  }

  function abortUnstarted(
    taskItem: QueuedTask,
    title: string,
    message: string,
    optionsSection?: string
  ): void {
    deps.runningRef.current = false
    deps.setRunning(false)
    deps.setRunStartedAt(null)
    deps.setCurrentTask(null)
    deps.currentTaskRef.current = null
    deps.setStatus(RUN_STATUS.FAILED)
    deps.setStatusDetail(null)
    deps.setLiveFeed([])
    const sessionId = deps.sessionRef.current
    if (sessionId) {
      void deps.markSessionComplete(sessionId, 'failed', message)
    }
    deps.setRunOutcome({ kind: 'failed', title, message, optionsSection })
    deps.setTask((current) => (current.trim() ? current : taskItem.text))
  }

  function finishBackgroundRun(payload: {
    runId: string
    status: RunAgentResult['status']
    result?: string
  }): void {
    if (deps.activeRunIdRef.current && deps.activeRunIdRef.current !== payload.runId) return
    if (!deps.runningRef.current) return
    deps.activeRunIdRef.current = null
    deps.runningRef.current = false
    deps.setRunning(false)
    deps.setRunStartedAt(null)
    deps.setCurrentTask(null)
    deps.currentTaskRef.current = null
    deps.setStatusDetail(null)
    deps.setLiveFeed([])
    const sessionId = deps.sessionRef.current
    const activityId = deps.activityRef.current
    if (payload.status === 'done') {
      deps.setStatus(RUN_STATUS.COMPLETED)
      if (sessionId) void deps.markSessionComplete(sessionId, 'success', payload.result)
      deps.setRunOutcome(
        payload.result?.trim()
          ? {
              kind: 'success',
              title: '已完成',
              message: payload.result.slice(0, 500),
            }
          : null
      )
      if (activityId) {
        void updateActivity(activityId, {
          status: 'success',
          detail: payload.result?.slice(0, 200),
        })
        deps.activityRef.current = null
      }
    } else if (payload.status === 'cancelled') {
      if (sessionId) void deps.markSessionComplete(sessionId, 'cancelled', payload.result)
      if (deps.status !== RUN_STATUS.CANCELLED) {
        deps.setStatus(RUN_STATUS.CANCELLED)
        deps.setRunOutcome({
          kind: 'cancelled',
          title: '已停止',
          message: payload.result ?? '已停止',
        })
      }
      if (activityId) deps.activityRef.current = null
    } else if (deps.status !== RUN_STATUS.FAILED && deps.status !== RUN_STATUS.CANCELLED) {
      deps.setStatus(RUN_STATUS.FAILED)
      if (sessionId) void deps.markSessionComplete(sessionId, 'failed', payload.result)
      deps.setRunOutcome({
        kind: 'failed',
        title: '运行失败',
        message: payload.result ?? payload.status,
      })
      if (activityId) {
        void updateActivity(activityId, {
          status: 'failed',
          detail: payload.result?.slice(0, 200) ?? payload.status,
        })
        deps.activityRef.current = null
      }
    }
    void processQueueHead()
  }

  async function processQueueHead(): Promise<void> {
    if (deps.processLockRef.current || deps.runningRef.current) return
    const queue = deps.pendingTasksRef.current
    if (!queue.length) return
    deps.processLockRef.current = true
    const [first, ...rest] = queue
    syncPendingTasks(rest)
    // Claim the run slot before any await so later enqueues go to follow_up / local pending merge.
    deps.runningRef.current = true
    deps.setRunning(true)
    try {
      await deps.startRun(first)
    } catch (error) {
      abortUnstarted(first, '启动失败', (error as Error).message)
    } finally {
      deps.processLockRef.current = false
    }
  }

  function enqueueTask(text?: string): void {
    const voice = deps.voiceRef.current
    const image = deps.imageRef.current
    const value = (text ?? deps.task).trim() || (voice ? '（语音）' : image ? '（图片）' : '')
    if (!value) return
    deps.setRunOutcome(null)
    const item = createQueuedTask(value)
    if (!item) return
    if (voice) {
      deps.pendingVoiceByTaskRef.current.set(item.id, voice)
      deps.voiceRef.current = null
      deps.setVoiceAttachment(null)
    }
    if (image) {
      deps.pendingImageByTaskRef.current.set(item.id, image)
      deps.imageRef.current = null
      deps.setImageAttachment(null)
    }
    if (text === undefined) deps.setTask('')
    syncPendingTasks([...deps.pendingTasksRef.current, item])
    const localPayload = {
      text: item.text,
      ...(voice
        ? {
            audioPath: voice.path,
            audioLabel: voice.label,
            audioDataUrl: voice.dataUrl,
          }
        : {}),
      ...(image ? { imageDataUrl: image.dataUrl, imageLabel: image.label } : {}),
    }
    if (deps.runningRef.current) {
      if (voice || image) {
        deps.appendLocal('user.task', localPayload)
        deps.recordSession({
          type: 'user.task',
          payload: {
            text: item.text,
            ...(voice
              ? { audioPath: voice.path, audioLabel: voice.label }
              : {}),
            ...(image ? { imageDataUrl: image.dataUrl, imageLabel: image.label } : {}),
          },
        })
      }
      void deps.agentRun
        .followUp(item)
        .then((r) => {
          if (r?.pending) deps.setQueuePending(r.pending)
          // If background has no activeRun yet, keep local pending — startRun merges it.
          if (r?.ok && Array.isArray(r.tasks)) syncPendingTasks(r.tasks)
        })
      return
    }
    void processQueueHead()
  }

  function enqueueSteer(): void {
    const text = deps.task.trim()
    if (!deps.running || !text) return
    // ask_user 等待中：纠偏即回复，避免 steer 入队后 HITL 永不解锁。
    if (deps.awaitingQuestion) {
      void replyHitl(text)
      return
    }
    void deps.agentRun.steer(text).then((r) => {
      if (r?.asHitl) {
        deps.setTask('')
        deps.setAwaitingQuestion(null)
        deps.setRunOutcome(null)
        deps.recordSession({ type: 'user.task', payload: { text } })
        deps.push(`↩ replied: ${text}`)
        if (r.pending) deps.setQueuePending(r.pending)
        return
      }
      if (!r?.ok) {
        deps.push('✗ 纠偏入队失败（无活动任务）')
        return
      }
      if (r.pending) deps.setQueuePending(r.pending)
      deps.push(`↩ 纠偏已入队: ${text}`)
      deps.setTask('')
    })
  }

  async function replyHitl(replyText?: string): Promise<void> {
    const text = (replyText ?? deps.task).trim()
    if (!deps.running || !text) return
    if (!deps.awaitingQuestion && deps.status !== RUN_STATUS.WAITING_USER) {
      return
    }
    deps.setTask('')
    const r = await deps.agentRun.reply(text)
    if (!r?.ok) {
      deps.push('✗ 回复未送达，请再试一次')
      deps.setTask(text)
      return
    }
    deps.recordSession({ type: 'user.task', payload: { text } })
    deps.push(`↩ replied: ${text}`)
    deps.setAwaitingQuestion(null)
    deps.setRunOutcome(null)
  }

  return {
    syncQueuePending,
    syncPendingTasks,
    refreshPendingTasks,
    replacePendingTasks,
    abortUnstarted,
    finishBackgroundRun,
    processQueueHead,
    enqueueTask,
    enqueueSteer,
    replyHitl,
  }
}
