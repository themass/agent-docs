import { useEffect } from 'react'
import { RUN_STATUS, type WorkspaceRunStatus } from '../lib/run-phase'

function parseWorkspaceRunStatus(value: string): WorkspaceRunStatus {
  return (Object.values(RUN_STATUS) as string[]).includes(value) ? (value as WorkspaceRunStatus) : RUN_STATUS.RUNNING
}
import type { MutableRefObject } from 'react'
import type { RunAgentResult } from '@naviforge/runtime'
import { createQueuedTask, type QueuedTask } from '@naviforge/runtime'
import { validateTraceRecord, type TraceRecord } from '@naviforge/session'
import type { Skill } from '@naviforge/skill-runtime'

import {
  loadCustomSkills,
  normalizeMaxAgentSteps,
  normalizeRunTimeoutMs,
  normalizeSameFailureLimit,
  normalizeTokenBudget,
  normalizeMaxInputTokens,
  normalizePrivacySettings,
  DEFAULT_PRIVACY,
  DEFAULT_MAX_AGENT_STEPS,
  DEFAULT_RUN_TIMEOUT_MS,
  DEFAULT_SAME_FAILURE_LIMIT,
  DEFAULT_TOKEN_BUDGET,
  DEFAULT_MAX_INPUT_TOKENS,
  STORAGE,
  type PrivacySettings,
} from '../lib/settings'
import { getActiveModelProfile, loadModelProfiles, type ModelProfilesStore } from '../lib/llm-profiles'
import { isNewApiLoggedIn, loadNewApiAuth, shouldSyncBootstrap } from '../lib/newapi-auth'
import { syncManagedProfilesFromNewApi } from '../lib/newapi-sync'
import type { PickedElement } from './workspace-helpers'
import { pickedLabel } from './workspace-helpers'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'

export function applyPrivacySettings(
  privacy: Partial<PrivacySettings> | undefined,
  setters: {
    setUseNetwork(value: boolean): void
    setAllowDomInject(value: boolean): void
    setAllowNetworkIntercept(value: boolean): void
    setHitlPolicy(value: 'strict' | 'balanced' | 'permissive'): void
    setRollbackUrlDrift(value: boolean): void
    setCaptureNetworkBodies(value: boolean): void
    setAllowMainProbe(value: boolean): void
    setVisionEnabled(value: boolean): void
    setEnforceSkillToolAllowlist(value: boolean): void
    setMaxAgentSteps(value: number): void
    setSameFailureLimit(value: number): void
    setRunTimeoutMs(value: number): void
    setTokenBudget(value: number): void
    setMaxInputTokens(value: number): void
    setIntakeMode(value: 'off' | 'auto' | 'always'): void
  }
): void {
  if (!privacy) return
  if (privacy.networkEnabled != null) setters.setUseNetwork(privacy.networkEnabled)
  if (privacy.allowDomInject != null) setters.setAllowDomInject(privacy.allowDomInject)
  if (privacy.allowNetworkIntercept != null) setters.setAllowNetworkIntercept(privacy.allowNetworkIntercept)
  if (privacy.hitlPolicy) setters.setHitlPolicy(privacy.hitlPolicy)
  if (privacy.rollbackUrlDrift != null) setters.setRollbackUrlDrift(privacy.rollbackUrlDrift)
  if (privacy.captureNetworkBodies != null) setters.setCaptureNetworkBodies(privacy.captureNetworkBodies)
  if (privacy.allowMainProbe != null) setters.setAllowMainProbe(privacy.allowMainProbe)
  if (privacy.visionEnabled != null) setters.setVisionEnabled(privacy.visionEnabled)
  if (privacy.enforceSkillToolAllowlist != null) {
    setters.setEnforceSkillToolAllowlist(privacy.enforceSkillToolAllowlist)
  }
  setters.setMaxAgentSteps(normalizeMaxAgentSteps(privacy.maxAgentSteps))
  setters.setSameFailureLimit(normalizeSameFailureLimit(privacy.sameFailureLimit))
  setters.setRunTimeoutMs(
    privacy.runTimeoutMs === 0
      ? 0
      : normalizeRunTimeoutMs(privacy.runTimeoutMs ?? DEFAULT_RUN_TIMEOUT_MS)
  )
  setters.setTokenBudget(
    privacy.tokenBudget === 0 ? 0 : normalizeTokenBudget(privacy.tokenBudget ?? DEFAULT_TOKEN_BUDGET)
  )
  setters.setMaxInputTokens(
    privacy.maxInputTokens === 0
      ? 0
      : normalizeMaxInputTokens(privacy.maxInputTokens ?? DEFAULT_MAX_INPUT_TOKENS)
  )
  setters.setIntakeMode(privacy.intakeMode ?? 'auto')
}

export function useWorkspaceBootstrap(deps: {
  setModelProfiles(value: ModelProfilesStore | null): void
  setDisabledSkills(value: string[]): void
  setCustomSkills(value: Skill[]): void
  refreshPlaybooks(): Promise<void>
  privacySetters: Parameters<typeof applyPrivacySettings>[1]
}): void {
  useEffect(() => {
    void (async () => {
      const auth = await loadNewApiAuth()
      if (auth.mode === 'managed' && isNewApiLoggedIn(auth)) {
        const profiles = await loadModelProfiles()
        const key = getActiveModelProfile(profiles).apiKey
        if (shouldSyncBootstrap(auth, { apiKeyEmpty: !key.trim() })) {
          await syncManagedProfilesFromNewApi()
        }
      }
      const profiles = await loadModelProfiles()
      deps.setModelProfiles(profiles)
    })()
    void chrome.storage.local.get(STORAGE.privacy).then((r) => {
      const raw = r[STORAGE.privacy] as Partial<PrivacySettings> | undefined
      if (!raw) {
        applyPrivacySettings(undefined, deps.privacySetters)
        return
      }
      const merged = { ...DEFAULT_PRIVACY, ...raw } as PrivacySettings
      const { privacy, changed } = normalizePrivacySettings(merged)
      if (changed) void chrome.storage.local.set({ [STORAGE.privacy]: privacy })
      applyPrivacySettings(privacy, deps.privacySetters)
    })
    const onStorageChange = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ) => {
      if (area !== 'local') return
      if (changes[STORAGE.llmProfiles]?.newValue) {
        deps.setModelProfiles(changes[STORAGE.llmProfiles].newValue as ModelProfilesStore)
      }
      if (changes[STORAGE.privacy]?.newValue) {
        applyPrivacySettings(changes[STORAGE.privacy].newValue as Partial<PrivacySettings>, deps.privacySetters)
      }
      if (changes[STORAGE.disabledSkills]?.newValue) {
        const disabled = changes[STORAGE.disabledSkills].newValue
        if (Array.isArray(disabled) && disabled.every((id: unknown) => typeof id === 'string')) {
          deps.setDisabledSkills(disabled as string[])
        }
      }
      if (changes[STORAGE.customSkills]?.newValue) {
        const skills = changes[STORAGE.customSkills].newValue
        if (Array.isArray(skills)) deps.setCustomSkills(skills as Skill[])
      }
    }
    chrome.storage.onChanged.addListener(onStorageChange)
    void deps.refreshPlaybooks()
    void chrome.storage.local.get(STORAGE.disabledSkills).then((r) => {
      const disabled = r[STORAGE.disabledSkills]
      if (Array.isArray(disabled) && disabled.every((id) => typeof id === 'string')) {
        deps.setDisabledSkills(disabled)
      }
    })
    void loadCustomSkills().then(deps.setCustomSkills)
    return () => chrome.storage.onChanged.removeListener(onStorageChange)
  }, [])
}

export function useWorkspaceAgentSync(deps: {
  tabRef: MutableRefObject<number | null>
  explainAfterPickRef: MutableRefObject<boolean>
  onRecord(record: TraceRecord): void
  onRunFinished(payload: {
    runId: string
    status: RunAgentResult['status']
    result?: string
  }): void
  syncPendingTasks(tasks: QueuedTask[]): void
  push(line: string): void
  setPickingElement(value: boolean): void
  setPickedElement(value: PickedElement | null): void
  setQueuedExplain(value: PickedElement | null): void
  setTask(updater: (current: string) => string): void
  setRunning(value: boolean): void
  setRunStartedAt(value: number | null): void
  setStatus(value: WorkspaceRunStatus): void
  setQueuePending(value: { steering: number; followUp: number }): void
  setTargetTab(value: { id: number; url?: string; title?: string } | null): void
}): void {
  useEffect(() => {
    const receive = (message: unknown) => {
      const data = message as {
        type?: string
        event?: TraceRecord
        runId?: string
        status?: RunAgentResult['status']
        answer?: string
        result?: { selector?: string; title?: string; tag?: string; text?: string }
      }
      if (data.type === 'AGENT_RUN_EVENT' && data.event) {
        try {
          deps.onRecord(validateTraceRecord(data.event))
        } catch {
          return
        }
      }
      if (
        data.type === 'AGENT_RUN_FINISHED' &&
        typeof data.runId === 'string' &&
        data.status
      ) {
        deps.onRunFinished({
          runId: data.runId,
          status: data.status,
          result: data.answer,
        })
      }
      if (data.type === 'NAVIFORGE_ELEMENT_PICK_CANCELLED') {
        deps.setPickingElement(false)
        deps.explainAfterPickRef.current = false
        deps.push('已取消元素选择')
      }
      if (data.type === 'NAVIFORGE_ELEMENT_PICKED' && data.result) {
        deps.setPickingElement(false)
        deps.setPickedElement(data.result)
        const label = pickedLabel(data.result)
        deps.push(`✓ 已选元素: ${label}${data.result.selector ? ` (${data.result.selector})` : ''}`)
        if (deps.explainAfterPickRef.current) {
          deps.explainAfterPickRef.current = false
          deps.setQueuedExplain(data.result)
          return
        }
        deps.setTask((current) => {
          const hint = `针对元素「${label}」`
          return current.trim() ? current : hint
        })
      }
    }
    chrome.runtime.onMessage.addListener(receive)
    void safeRuntimeSendMessage<{
        active?: boolean
        status?: string
        tabId?: number
        events?: TraceRecord[]
        tasks?: QueuedTask[]
        followUps?: string[]
        pending?: { steering: number; followUp: number }
      }>({ type: 'AGENT_RUN', action: 'status' }).then((state) => {
        if (!state?.active) return
        deps.setRunning(true)
        deps.setRunStartedAt(Date.now())
        if (state.status) deps.setStatus(parseWorkspaceRunStatus(state.status))
        if (state.pending) deps.setQueuePending(state.pending)
        if (Array.isArray(state.tasks)) deps.syncPendingTasks(state.tasks)
        if (state.tabId) {
          deps.tabRef.current = state.tabId
          void chrome.tabs.get(state.tabId).then((tab) => {
            deps.setTargetTab({ id: state.tabId!, url: tab.url, title: tab.title })
          })
        }
        for (const event of state.events ?? []) deps.onRecord(event)
      })
      .catch(() => {})
    return () => chrome.runtime.onMessage.removeListener(receive)
  }, [])
}

export function useQueuedExplainEffect(
  queuedExplain: PickedElement | null,
  setQueuedExplain: (value: PickedElement | null) => void,
  explainPickedElement: (target?: PickedElement) => Promise<void>
): void {
  useEffect(() => {
    if (!queuedExplain) return
    const element = queuedExplain
    setQueuedExplain(null)
    void explainPickedElement(element)
  }, [queuedExplain])
}
