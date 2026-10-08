import { useEffect, useState } from 'react'

import { ChatHeader } from '../components/chat/chat-header'
import { Composer } from '../components/chat/composer'
import { useI18n } from '../i18n'
import { CameraPage } from '../components/chat/camera-page'
import { ContextBar } from '../components/chat/context-bar'
import { HitlReplyModal } from '../components/chat/hitl-reply-modal'
import { MessageList } from '../components/chat/message-list'
import { AuthStatusBar } from '../components/auth-status-bar'
import { TaskQueuePanel } from '../components/chat/task-queue-panel'
import { shotAskFromText } from '../lib/image-ask'
import { RUN_STATUS, isWorkspaceRunning } from '../lib/run-phase'
import { openOptionsPage, openWorkspaceTab } from '../lib/surface-launch'
import { AgentCapabilitiesSheet } from '../components/chat/agent-capabilities-sheet'
import { privacyFromWorkspaceState } from '../components/chat/agent-capabilities-editor'
import { HistoryDrawer } from './history-drawer'
import { headerStatusDetail } from './live-thinking'
import { preventImeFocusSteal } from '../lib/ime-safe-surface'
import { useAgentWorkspace } from './use-agent-workspace'

export function ChatApp({ variant = 'panel' }: { variant?: 'panel' | 'wide' }) {
  const { t } = useI18n()
  const wide = variant === 'wide'
  const ws = useAgentWorkspace()
  const [historyOpen, setHistoryOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [capabilitiesOpen, setCapabilitiesOpen] = useState(false)

  async function handleSubmit(): Promise<void> {
    if (hitlWaiting) return
    if (ws.awaitingQuestion) {
      void ws.replyHitl()
      return
    }
    if (ws.running) {
      ws.enqueueTask()
      return
    }
    if (ws.imageAttachment || ((ws.pageAskMode || shotAskFromText(ws.task)) && !ws.voiceAttachment)) {
      await ws.askAboutImage()
      return
    }
    ws.enqueueTask()
  }

  function handleSteer(): void {
    if (hitlWaiting) return
    if (ws.awaitingQuestion) {
      void ws.replyHitl()
      return
    }
    ws.enqueueSteer()
  }

  function handleFollowUp(): void {
    if (ws.awaitingQuestion || !ws.running) return
    ws.enqueueTask()
  }

  function openAgentSettings(): void {
    void openOptionsPage('settings')
  }

  function openPrivacySettings(): void {
    setCapabilitiesOpen(false)
    void openOptionsPage('settings', 'agent')
  }

  function openWide(): void {
    void openWorkspaceTab()
  }

  async function copySession(): Promise<void> {
    const md = ws.exportMarkdown()
    await navigator.clipboard.writeText(md)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const busy = ws.running || ws.pageAskBusy
  const headerDetail = headerStatusDetail(isWorkspaceRunning(ws.status) || busy, ws.statusDetail)
  const hitlWaiting =
    ws.status === RUN_STATUS.WAITING_USER && Boolean(ws.awaitingQuestion)
  const placeholder = hitlWaiting
      ? t('chat.hitl.placeholder')
      : ws.awaitingQuestion
    ? t('chat.placeholderReply')
    : ws.voiceAttachment
      ? t('chat.placeholderVoice')
      : ws.imageAttachment
        ? t('chat.placeholderImage')
        : ws.pageAskMode
          ? t('chat.placeholderPage')
          : ws.running
            ? t('chat.placeholderFollow')
            : t('chat.placeholder')

  useEffect(() => {
    if (!ws.tabPickerOpen) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') ws.setTabPickerOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [ws.tabPickerOpen, ws.setTabPickerOpen])

  return (
    <div
      className={`relative flex h-full min-h-screen flex-col bg-background ${
        wide ? 'chat-wide' : 'chat-panel'
      }`}
      onMouseDown={preventImeFocusSteal}
    >
      <ChatHeader
        status={ws.status}
        statusDetail={headerDetail}
        wide={wide}
        onNewChat={() => void ws.startNewThread()}
        onHistory={() => setHistoryOpen(true)}
        onCopy={() => void copySession()}
        onSettings={openAgentSettings}
        onOpenWide={wide ? undefined : openWide}
      />

      <ContextBar
        targetTab={ws.targetTab}
        modelName={ws.activeProfile?.name ?? ws.activeProfile?.model}
        capabilityPrivacy={privacyFromWorkspaceState({
          useNetwork: ws.useNetwork,
          captureNetworkBodies: ws.captureNetworkBodies,
          allowDomInject: ws.allowDomInject,
          allowNetworkIntercept: ws.allowNetworkIntercept,
          allowMainProbe: ws.allowMainProbe,
          visionEnabled: ws.visionEnabled,
        })}
        onOpenCapabilities={() => setCapabilitiesOpen(true)}
        threadTitle={ws.activeThread?.title}
        locked={ws.running}
        wide={wide}
        tabPickerOpen={ws.tabPickerOpen}
        pickedElement={ws.pickedElement}
        lastPlaybookId={ws.activeThread?.lastPlaybookId}
        pageSignalsPreview={ws.pageSignalsPreview}
        onSwitchTab={() => {
          if (ws.tabPickerOpen) {
            ws.setTabPickerOpen(false)
            return
          }
          void ws.openTabPicker()
        }}
        onClearPick={ws.clearPickedElement}
        onReplayPlaybook={() => void ws.replayThreadPlaybook()}
      />

      {ws.tabPickerOpen ? (
        <div className="relative z-10 mx-3 mt-2 max-h-48 overflow-y-auto rounded-lg border-2 border-primary/30 bg-primary/5 p-3 text-base shrink-0 shadow-sm">
          <div className="mb-2 flex items-center justify-between gap-2">
            <strong className="text-foreground">选择控制标签</strong>
            <button
              type="button"
              className="shrink-0 rounded-md px-2 py-0.5 text-xs text-muted-foreground hover:bg-background hover:text-foreground"
              onClick={() => ws.setTabPickerOpen(false)}
            >
              取消
            </button>
          </div>
          {!ws.allTabs.length ? (
            <p className="text-sm text-muted-foreground">没有可切换的普通网页标签（chrome:// 页面不可选）</p>
          ) : (
            ws.allTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`block w-full text-left py-2 hover:bg-background/80 truncate rounded px-2 ${
                  tab.id === ws.targetTab?.id ? 'bg-background font-medium' : ''
                }`}
                onClick={() => {
                  void ws.switchToTab(tab.id, tab.windowId)
                }}
              >
                #{tab.id} · {tab.title || tab.url}
                {tab.active ? ' · 当前活动' : ''}
              </button>
            ))
          )}
        </div>
      ) : null}

      <MessageList
        events={ws.events}
        running={busy}
        task={ws.task}
        status={ws.status}
        statusDetail={ws.statusDetail}
        runStartedAt={ws.runStartedAt}
        topVideos={ws.topVideos}
        resultsMarked={ws.resultsMarked}
        resultsStale={ws.resultsStale}
        listWarnings={ws.listWarnings}
        runOutcome={ws.runOutcome}
        wide={wide}
        onFocusVideo={(video) => void ws.focusMarkedVideo(video)}
        onRequeue={(intent) => ws.enqueueTask(intent)}
        showThinking={busy && !ws.awaitingQuestion && !hitlWaiting}
        thinkingDetail={headerDetail ?? ws.statusDetail}
        thinkingReasoning={ws.thinkingReasoning}
        liveFeed={ws.liveFeed}
      />

      {copied ? (
        <p className="text-center text-xs text-green-600 py-1">已复制 Markdown</p>
      ) : null}

      <div className="shrink-0 border-t border-border/60 bg-background">
        <TaskQueuePanel
          currentTask={ws.currentTask}
          pendingTasks={ws.pendingTasks}
          steeringCount={ws.queuePending.steering}
          running={ws.running}
          onChangePending={ws.replacePendingTasks}
          onSteer={handleSteer}
          onFollowUp={handleFollowUp}
          queueDisabled={!ws.task.trim()}
          onPause={ws.togglePause}
          paused={ws.paused}
        />

        <Composer
          value={ws.task}
          onChange={ws.setTask}
          onSubmit={() => void handleSubmit()}
          onSlashCommand={(name, body) => ws.runSlashCommand(name, body)}
          slashCommands={ws.slashCommands}
          onSteer={handleSteer}
          onStop={ws.stop}
          running={busy}
          awaitingQuestion={Boolean(ws.awaitingQuestion)}
          placeholder={placeholder}
          wide={wide}
          pageAskMode={ws.pageAskMode}
          onPageAskModeChange={ws.setPageAskMode}
          onSummarize={() => void ws.summarizeCurrentPage()}
          onExplainPick={() => void ws.explainPickedElement()}
          onCopyArticle={() => void ws.copyPageArticle()}
          hasPickedElement={Boolean(ws.pickedElement)}
          onPick={() => void ws.pickElement()}
          pickingElement={ws.pickingElement}
          pickDisabled={busy && !ws.awaitingQuestion}
          actingLabel={
            busy && !ws.awaitingQuestion && !hitlWaiting ? null : ws.statusDetail
          }
          imageAttachment={ws.imageAttachment}
          onClearAttachment={() => ws.setImageAttachment(null)}
          recentShots={ws.recentShots}
          onRefreshShots={() => void ws.refreshRecentShots()}
          onAttachViewport={() => void ws.attachViewport()}
          onAttachShot={(path) => void ws.attachShot(path)}
          onAttachFile={(file) => void ws.attachFile(file)}
          onLaunchScreenshotStudio={() => void ws.launchScreenshotStudio()}
          voiceAttachment={ws.voiceAttachment}
          onClearVoice={() => ws.clearVoice()}
          onAttachVoice={(clip) => ws.attachVoice(clip)}
          onOpenCamera={() => {
            if (busy && !ws.awaitingQuestion) return
            setHistoryOpen(false)
            setCameraOpen(true)
          }}
          shotAskHint={Boolean(!ws.imageAttachment && shotAskFromText(ws.task))}
          modelProfiles={ws.modelProfiles?.profiles ?? []}
          activeProfileId={ws.activeProfile?.id}
          onSelectModelProfile={(id) => void ws.selectModelProfile(id)}
          contextBreakdown={ws.contextBreakdown}
          runTotal={ws.tokenUsage?.runTotal}
          runTokenBudget={ws.runTokenBudget}
        />
        <AuthStatusBar variant="chat" />
      </div>

      {hitlWaiting && ws.awaitingQuestion ? (
        <HitlReplyModal
          question={ws.awaitingQuestion}
          onSubmit={(text) => void ws.replyHitl(text)}
          onStop={ws.stop}
        />
      ) : null}

      {cameraOpen ? (
        <CameraPage
          wide={wide}
          onClose={() => setCameraOpen(false)}
          onUse={(dataUrl) => {
            ws.setImageAttachment({ dataUrl, label: '摄像头' })
            setCameraOpen(false)
          }}
        />
      ) : null}

      <HistoryDrawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onResume={(payload) => void ws.resumeSession(payload)}
      />

      <AgentCapabilitiesSheet
        open={capabilitiesOpen}
        onClose={() => setCapabilitiesOpen(false)}
        locked={busy}
        workspacePrivacy={{
          useNetwork: ws.useNetwork,
          captureNetworkBodies: ws.captureNetworkBodies,
          allowDomInject: ws.allowDomInject,
          allowNetworkIntercept: ws.allowNetworkIntercept,
          allowMainProbe: ws.allowMainProbe,
          visionEnabled: ws.visionEnabled,
        }}
        onOpenFullSettings={() => openPrivacySettings()}
      />
    </div>
  )
}
