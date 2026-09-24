import { useEffect, useMemo, useRef, useState } from 'react'
import { type Skill } from '@naviforge/skill-runtime'

import {
  getActiveModelProfile,
  saveModelProfiles,
  setActiveModelProfile,
  type ModelProfilesStore,
} from '../lib/llm-profiles'
import { sessionToChatEvents } from './chat-events'
import { latestReasoning } from './live-thinking'
import {
  exportSessionMarkdown,
  type PickedElement,
} from './workspace-helpers'
import { createOneShotActions } from './workspace-one-shot'
import { createAttachmentActions } from './workspace-attachments'
import { createPlaybookActions } from './workspace-playbook-actions'
import {
  useQueuedExplainEffect,
  useWorkspaceBootstrap,
} from './workspace-effects'
import { useWorkspacePrivacyState } from './workspace-privacy-state'
import { useWorkspaceRun } from './use-workspace-run'
import { latestContextBreakdown } from '@naviforge/context-metrics'
import { latestIntakeSession } from '../modules/intake-ui'
import { useI18n } from '../i18n'
import { createSlashCommandRunner } from './workspace-slash'
import { buildSlashCommandRegistry } from '../components/chat/composer-slash-registry'
import { useScreenshotStudioComposerBridge } from '../modules/screenshot-studio'
import { SCREENSHOT_STUDIO_MESSAGE } from '../modules/screenshot-studio/messages'

/**
 * React state and subscription composition for the public workspace hook.
 *
 * Imperative persistence, playbook, and run primitives are delegated to their
 * focused controllers; this module composes them with UI state.
 */
export function useWorkspaceComposition() {
  const [modelProfiles, setModelProfiles] = useState<ModelProfilesStore | null>(null)
  const [task, setTask] = useState('')
  const privacy = useWorkspacePrivacyState()
  const {
    useNetwork,
    allowDomInject,
    allowNetworkIntercept,
    hitlPolicy,
    rollbackUrlDrift,
    captureNetworkBodies,
    allowMainProbe,
    visionEnabled,
    maxAgentSteps,
    sameFailureLimit,
    runTimeoutMs,
    tokenBudget,
    maxInputTokens,
    intakeMode,
    enforceSkillToolAllowlist,
    privacySetters,
  } = privacy
  const [pageAskMode, setPageAskMode] = useState(false)
  const [pageAskBusy, setPageAskBusy] = useState(false)
  const [imageAttachment, setImageAttachment] = useState<{ dataUrl: string; label: string } | null>(
    null
  )
  const [voiceAttachment, setVoiceAttachment] = useState<{
    dataUrl: string
    path?: string
    label: string
  } | null>(null)
  const voiceRef = useRef<{ dataUrl: string; path?: string; label: string } | null>(null)
  const imageRef = useRef<{ dataUrl: string; label: string } | null>(null)
  const pendingVoiceByTaskRef = useRef(
    new Map<string, { dataUrl: string; path?: string; label: string }>()
  )
  const pendingImageByTaskRef = useRef(
    new Map<string, { dataUrl: string; label: string }>()
  )
  const [recentShots, setRecentShots] = useState<Array<{ path: string; name: string; thumb?: string }>>(
    []
  )
  const pageAskAbortRef = useRef<AbortController | null>(null)
  const explainAfterPickRef = useRef(false)
  const [queuedExplain, setQueuedExplain] = useState<PickedElement | null>(null)
  const [targetTab, setTargetTab] = useState<{
    id: number
    url?: string
    title?: string
    windowId?: number
  } | null>(null)
  const [tabPickerOpen, setTabPickerOpen] = useState(false)
  const [allTabs, setAllTabs] = useState<
    Array<{ id: number; title?: string; url?: string; active: boolean; windowId?: number }>
  >([])
  const [privacyToast, setPrivacyToast] = useState<string | null>(null)
  const [playbooks, setPlaybooks] = useState<import('@naviforge/playbook').Playbook[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [playbookDraft, setPlaybookDraft] = useState('')
  const [playbookInputs, setPlaybookInputs] = useState<Record<string, string>>({})
  const [disabledSkills, setDisabledSkills] = useState<string[]>([])
  const [customSkills, setCustomSkills] = useState<Skill[]>([])
  const [threads, setThreads] = useState<import('../lib/thread-model').AgentThread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string>('')
  const [pickedElement, setPickedElement] = useState<PickedElement | null>(null)
  const [pickingElement, setPickingElement] = useState(false)
  const traceRef = useRef<HTMLPreElement | null>(null)

  const run = useWorkspaceRun({
    task,
    setTask,
    threads,
    setThreads,
    activeThreadId,
    setActiveThreadId,
    targetTab,
    setTargetTab,
    setAllTabs,
    setTabPickerOpen,
    pageAskBusy,
    setPageAskBusy,
    pageAskAbortRef,
    voiceRef,
    imageRef,
    pendingVoiceByTaskRef,
    pendingImageByTaskRef,
    explainAfterPickRef,
    setPickedElement,
    setPickingElement,
    setQueuedExplain,
    setImageAttachment,
    setVoiceAttachment,
    setPrivacyToast,
    customSkills,
    disabledSkills,
    modelProfiles,
    useNetwork,
    allowDomInject,
    allowNetworkIntercept,
    hitlPolicy,
    rollbackUrlDrift,
    captureNetworkBodies,
    allowMainProbe,
    visionEnabled,
    maxAgentSteps,
    sameFailureLimit,
    runTimeoutMs,
    tokenBudget,
    maxInputTokens,
    intakeMode,
    enforceSkillToolAllowlist,
  })

  const { locale } = useI18n()

  const events = useMemo(() => sessionToChatEvents(run.records, locale), [run.records, locale])
  const contextBreakdown = useMemo(() => latestContextBreakdown(run.records), [run.records])
  const intakeSession = useMemo(() => latestIntakeSession(run.records), [run.records])
  const thinkingReasoning = useMemo(() => latestReasoning(run.records), [run.records])
  const activeProfile = modelProfiles ? getActiveModelProfile(modelProfiles) : null

  useEffect(() => {
    imageRef.current = imageAttachment
  }, [imageAttachment])

  const attachmentActions = createAttachmentActions({
    pageAskBusy,
    runningRef: run.runningRef,
    voiceRef,
    setRecentShots,
    setImageAttachment,
    setVoiceAttachment,
    setRunOutcome: run.setRunOutcome,
    bindActiveTab: run.bindActiveTab,
  })

  const oneShotActions = createOneShotActions({
    llm: run.llm,
    task,
    pageAskBusy,
    pickedElement,
    imageAttachment,
    runningRef: run.runningRef,
    pageAskAbortRef,
    explainAfterPickRef,
    setPageAskBusy,
    setStatus: run.setStatus,
    setStatusDetail: run.setStatusDetail,
    setTask,
    setRunOutcome: run.setRunOutcome,
    setTokenUsage: run.setTokenUsage,
    setImageAttachment,
    appendLocal: run.appendLocal,
    push: run.push,
    bindActiveTab: run.bindActiveTab,
    pickElement: run.pickElement,
  })

  const slashCommands = useMemo(
    () => buildSlashCommandRegistry(run.enabledSkills),
    [run.enabledSkills]
  )

  const slashActions = createSlashCommandRunner({
    registry: slashCommands,
    enabledSkills: run.enabledSkills,
    setTask,
    setPageAskMode,
    appendLocal: run.appendLocal,
    enqueueTask: run.enqueueTask,
    summarizeCurrentPage: oneShotActions.summarizeCurrentPage,
    explainPickedElement: oneShotActions.explainPickedElement,
    copyPageArticle: oneShotActions.copyPageArticle,
    askAboutCurrentPage: oneShotActions.askAboutCurrentPage,
  })

  const selected = playbooks.find((p) => p.id === selectedId) ?? null
  const activeThread = threads.find((item) => item.id === activeThreadId) ?? null

  const playbookActions = createPlaybookActions({
    selectedId,
    playbookDraft,
    playbookInputs,
    disabledSkills,
    useNetwork,
    captureNetworkBodies,
    playbooks,
    activeThread,
    selected,
    setPlaybooks,
    setSelectedId,
    setDisabledSkills,
    setTask,
    push: run.push,
    bindActiveTab: run.bindActiveTab,
  })

  useWorkspaceBootstrap({
    setModelProfiles,
    setDisabledSkills,
    setCustomSkills,
    refreshPlaybooks: playbookActions.refreshPlaybooks,
    privacySetters,
  })

  useScreenshotStudioComposerBridge(setImageAttachment)

  useEffect(() => {
    const onMessage = (message: unknown) => {
      if (!message || typeof message !== 'object') return
      const payload = message as { type?: string; dataUrl?: string; label?: string }
      if (payload.type !== SCREENSHOT_STUDIO_MESSAGE.attach) return
      if (typeof payload.dataUrl !== 'string') return
      setImageAttachment({
        dataUrl: payload.dataUrl,
        label: typeof payload.label === 'string' ? payload.label : '截图',
      })
    }
    chrome.runtime.onMessage.addListener(onMessage)
    return () => chrome.runtime.onMessage.removeListener(onMessage)
  }, [])

  useEffect(() => {
    if (run.traceOpen && traceRef.current) {
      traceRef.current.scrollTop = traceRef.current.scrollHeight
    }
  }, [run.records, run.traceOpen])

  useEffect(() => {
    if (!selected) {
      setPlaybookDraft('')
      setPlaybookInputs({})
      return
    }
    setPlaybookDraft(JSON.stringify(selected, null, 2))
    setPlaybookInputs(
      Object.fromEntries(
        Object.entries(selected.inputs ?? {}).map(([name, definition]) => [
          name,
          definition.default ?? '',
        ])
      )
    )
  }, [selectedId, playbooks])

  useQueuedExplainEffect(queuedExplain, setQueuedExplain, oneShotActions.explainPickedElement)

  async function selectModelProfile(profileId: string): Promise<void> {
    if (!modelProfiles) return
    const next = setActiveModelProfile(modelProfiles, profileId)
    setModelProfiles(next)
    await saveModelProfiles(next)
  }

  function exportMarkdown(): string {
    return exportSessionMarkdown(events, task, activeProfile?.model)
  }

  return {
    task,
    setTask,
    events,
    status: run.status,
    statusDetail: run.statusDetail,
    liveFeed: run.liveFeed,
    thinkingReasoning,
    running: run.running,
    runStartedAt: run.runStartedAt,
    paused: run.paused,
    awaitingQuestion: run.awaitingQuestion,
    runOutcome: run.runOutcome,
    topVideos: run.topVideos,
    resultsMarked: run.resultsMarked,
    resultsStale: run.resultsStale,
    listWarnings: run.listWarnings,
    pageSignalsPreview: run.pageSignalsPreview,
    tokenUsage: run.tokenUsage,
    contextBreakdown,
    intakeSession,
    runTokenBudget: tokenBudget,
    targetTab,
    tabPickerOpen,
    setTabPickerOpen,
    allTabs,
    pickedElement,
    pickingElement,
    clearPickedElement: run.clearPickedElement,
    readinessItems: run.readinessItems,
    privacyToast,
    blockedQuestions: run.blockedQuestions,
    activeThread,
    threads,
    activeThreadId,
    setActiveThreadId,
    queuePending: run.queuePending,
    pendingTasks: run.pendingTasks,
    currentTask: run.currentTask,
    replacePendingTasks: run.replacePendingTasks,
    refreshPendingTasks: run.refreshPendingTasks,
    enqueueTask: run.enqueueTask,
    modelProfiles,
    activeProfile,
    selectModelProfile,
    enabledSkills: run.enabledSkills,
    playbooks,
    useNetwork,
    pageAskMode,
    setPageAskMode,
    pageAskBusy,
    imageAttachment,
    setImageAttachment,
    voiceAttachment,
    attachVoice: attachmentActions.attachVoice,
    clearVoice: attachmentActions.clearVoice,
    recentShots,
    refreshRecentShots: attachmentActions.refreshRecentShots,
    attachViewport: attachmentActions.attachViewport,
    attachShot: attachmentActions.attachShot,
    attachFile: attachmentActions.attachFile,
    launchScreenshotStudio: attachmentActions.launchScreenshotStudio,
    askAboutImage: oneShotActions.askAboutImage,
    askAboutCurrentPage: oneShotActions.askAboutCurrentPage,
    summarizeCurrentPage: oneShotActions.summarizeCurrentPage,
    explainPickedElement: oneShotActions.explainPickedElement,
    copyPageArticle: oneShotActions.copyPageArticle,
    runSlashCommand: slashActions.runSlashCommand,
    slashCommands,
    start: run.enqueueTask,
    stop: run.stop,
    togglePause: run.togglePause,
    enqueueSteer: run.enqueueSteer,
    replyHitl: run.replyHitl,
    startNewThread: run.startNewThread,
    openTabPicker: run.openTabPicker,
    switchToTab: run.switchToTab,
    bindActiveTab: run.bindActiveTab,
    pickElement: run.pickElement,
    focusMarkedVideo: run.focusMarkedVideo,
    replayThreadPlaybook: playbookActions.replayThreadPlaybook,
    recoverObserveFromPlaybook: playbookActions.recoverObserveFromPlaybook,
    exportMarkdown,
    resumeSession: run.resumeSession,
  }
}
