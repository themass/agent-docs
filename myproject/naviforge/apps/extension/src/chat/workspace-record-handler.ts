import type { MutableRefObject, SetStateAction } from 'react'
import { formatActingDetail } from '@naviforge/runtime'
import { isContinuationMessage } from '@naviforge/session'
import { RUN_STATUS, type WorkspaceRunStatus } from '../lib/run-phase'
import type { TraceRecord } from '@naviforge/session'

import { appendActivityEvent } from '../lib/activity-store'
import { clipLiveLine, pushLiveFeed } from './live-thinking'
import type { TopVideo } from './workspace-helpers'

export type RecordHandlerDeps = {
  activityRef: MutableRefObject<string | null>
  currentTaskRef: MutableRefObject<{ id: string; text: string } | null>
  lastRunModeRef: MutableRefObject<string | undefined>
  ingestRecord(record: TraceRecord): void
  persistThreadMemory(
    taskText: string,
    resultText: string,
    mode?: string,
    opts?: { setGoal?: boolean }
  ): Promise<void>
  setStatus(value: WorkspaceRunStatus): void
  setStatusDetail(value: string | null | ((prev: string | null) => string | null)): void
  setLiveFeed(value: SetStateAction<string[]>): void
  setTokenUsage(value: {
    lastPrompt: number
    lastCompletion: number
    runTotal: number
  } | null): void
  setTopVideos(value: TopVideo[]): void
  setResultsMarked(value: boolean): void
  setResultsStale(value: boolean): void
  setListWarnings(value: { missed?: string[]; offscreen?: string[]; shortfall?: string }): void
  setPageSignalsPreview(value: string | null): void
  setAwaitingQuestion(value: string | null): void
  setRunOutcome(value: {
    kind: 'success' | 'failed' | 'blocked' | 'waiting' | 'cancelled'
    title: string
    message: string
  } | null): void
  setRunning(value: boolean): void
  setRunStartedAt(value: number | null): void
  setTraceOpen(value: boolean): void
  runningRef: MutableRefObject<boolean>
}

function feed(deps: RecordHandlerDeps, line: string): void {
  deps.setLiveFeed((prev) => pushLiveFeed(prev, line))
}

function toolPlanDetail(tool: string, args?: Record<string, unknown>): string {
  if (tool === 'skill_load') {
    const id = typeof args?.id === 'string' ? args.id : ''
    return id ? `准备加载 skill：${id}` : '准备加载 skill…'
  }
  return formatActingDetail(tool, args, 'zh-CN')
}

/** Map TraceRecord events to workspace UI state transitions. */
export function createWorkspaceRecordHandler(deps: RecordHandlerDeps) {
  return function onRecord(e: TraceRecord): void {
    const activityId = deps.activityRef.current
    deps.ingestRecord(e)

    switch (e.type) {
      case 'run.mode':
        deps.lastRunModeRef.current = e.payload.mode
        if (e.payload.detail) {
          deps.setStatusDetail(e.payload.detail)
          feed(deps, e.payload.detail)
        }
        break
      case 'run.note':
        if (e.payload.topic === 'status' && e.payload.text.trim()) {
          deps.setStatusDetail(e.payload.text)
          feed(deps, e.payload.text)
        } else if (e.payload.topic === 'subtask' && e.payload.text.trim()) {
          feed(deps, e.payload.text)
          deps.setStatusDetail(e.payload.text)
        } else if (e.payload.topic === 'page_signals' && e.payload.text.trim()) {
          deps.setPageSignalsPreview(e.payload.text)
        }
        break
      case 'run.log':
        if (activityId) {
          void appendActivityEvent(activityId, {
            at: Date.now(),
            level: 'info',
            message: e.payload.message,
          })
        }
        break
      case 'model.turn': {
        const call = e.payload.call
        if (call?.tool) {
          deps.setStatusDetail(toolPlanDetail(call.tool, call.arguments))
          feed(deps, toolPlanDetail(call.tool, call.arguments))
        } else {
          const plan = e.payload.summary
            ? `模型计划：${clipLiveLine(e.payload.summary, 80)}`
            : '模型已返回计划'
          deps.setStatusDetail(plan)
          feed(deps, plan)
        }
        if (activityId) {
          void appendActivityEvent(activityId, {
            at: Date.now(),
            level: 'info',
            message: `${call ? 'plan' : 'think'}: ${e.payload.summary}`,
          })
        }
        break
      }
      case 'metrics.tokens':
        deps.setTokenUsage({
          lastPrompt: e.payload.prompt,
          lastCompletion: e.payload.completion,
          runTotal: e.payload.runTotal,
        })
        break
      case 'tool.result': {
        const detail = e.payload.ok ? `已完成：${e.payload.tool}` : `工具失败：${e.payload.tool}`
        if (e.payload.tool === 'skill_load' && e.payload.ok) {
          const id = typeof e.payload.arguments?.id === 'string' ? e.payload.arguments.id : ''
          feed(deps, id ? `Skill 已加载 · ${id}` : 'Skill 已加载')
        } else if (e.payload.tool === 'system_spawn_readonly_tasks' && e.payload.ok) {
          feed(deps, '已启动只读子任务')
        } else if (e.payload.tool === 'tabs_open' && e.payload.ok) {
          feed(deps, '正在打开页面…')
        } else if (e.payload.tool === 'dom_navigate' && e.payload.ok) {
          feed(deps, '页面导航完成')
        } else {
          feed(deps, detail)
        }
        deps.setStatusDetail(
          e.payload.ok
            ? e.payload.tool === 'system_spawn_readonly_tasks'
              ? '子任务运行中…'
              : '继续执行…'
            : detail
        )
        if ((e.payload.tool === 'dom_mark_topn' || e.payload.tool === 'dom_extract_content') && e.payload.ok) {
          const data = e.payload.data as {
            items?: TopVideo[]
            shortfall?: string
            missed?: string[]
            offscreen?: string[]
          }
          deps.setTopVideos(
            data.items?.map((item) => ({
              ...item,
              label: item.label ?? `TOP${item.index}`,
              title: item.title ?? '',
              index: item.index ?? 0,
            })) ?? []
          )
          deps.setResultsMarked(e.payload.tool === 'dom_mark_topn')
          deps.setResultsStale(false)
          deps.setListWarnings({
            shortfall: data.shortfall,
            missed: data.missed,
            offscreen: data.offscreen,
          })
        }
        break
      }
      case 'context.compaction':
        feed(deps, '正在压缩上下文…')
        break
      case 'run.result':
        deps.setAwaitingQuestion(null)
        deps.setStatusDetail(null)
        deps.setLiveFeed([])
        deps.setPageSignalsPreview(null)
        if (deps.currentTaskRef.current && e.payload.text) {
          const taskText = deps.currentTaskRef.current.text
          void deps.persistThreadMemory(
            taskText,
            e.payload.text,
            deps.lastRunModeRef.current,
            { setGoal: !isContinuationMessage(taskText) }
          )
        }
        break
      case 'run.ask':
        deps.setStatus(RUN_STATUS.WAITING_USER)
        deps.setStatusDetail('等待你回复')
        deps.setAwaitingQuestion(e.payload.question)
        deps.setRunOutcome({
          kind: 'waiting',
          title: e.payload.wait === 'captcha' ? '等待人机验证' : '等待你的回复',
          message: e.payload.question,
        })
        break
      case 'run.error': {
        const cancelled = e.payload.code === 'cancelled'
        deps.setStatus(cancelled ? RUN_STATUS.CANCELLED : RUN_STATUS.FAILED)
        deps.runningRef.current = false
        deps.setRunning(false)
        deps.setRunStartedAt(null)
        deps.setAwaitingQuestion(null)
        deps.setStatusDetail(null)
        deps.setLiveFeed([])
        deps.setPageSignalsPreview(null)
        if (!cancelled) deps.setTraceOpen(true)
        deps.setRunOutcome({
          kind: cancelled ? 'cancelled' : 'failed',
          title: cancelled ? '已停止' : '运行失败',
          message: e.payload.message,
        })
        if (activityId && !cancelled) {
          void appendActivityEvent(activityId, {
            at: Date.now(),
            level: 'error',
            message: e.payload.message,
          })
        }
        if (deps.currentTaskRef.current && e.payload.message && !cancelled) {
          const taskText = deps.currentTaskRef.current.text
          void deps.persistThreadMemory(
            taskText,
            e.payload.message,
            deps.lastRunModeRef.current,
            { setGoal: !isContinuationMessage(taskText) }
          )
        }
        break
      }
      case 'run.recovery': {
        const line = `${e.payload.strategy} · ${clipLiveLine(e.payload.diagnostic, 80)}`
        feed(deps, line)
        if (activityId) {
          void appendActivityEvent(activityId, {
            at: Date.now(),
            level: 'recovery',
            message: `${e.payload.strategy}: ${e.payload.diagnostic}`,
          })
        }
        break
      }
    }
  }
}
