import {
  attachNetwork,
  cancelNetworkWaits,
  clearIntercepts,
  clearNetwork,
  detachNetwork,
  digestNetwork,
  ensureNetworkListeners,
  listIntercepts,
  verifyNetworkDebuggerAttached,
  listNetwork,
  listScriptBodyPreviews,
  fetchMissingScriptBodies,
  segmentNetworkTab,
  setIntercepts,
  waitNetwork,
  getNetworkBody,
} from '../lib/network-recorder'
import {
  bindToolkitTabNetwork,
  ensureTabNetworkSessionListeners,
  releaseRunNetwork,
} from '../lib/network-session'
import { startHostBridge } from '../lib/host-bridge'
import { attachNetworkWithRecovery } from '../lib/network-attach-recovery'
import { runSupervisor } from '../lib/run-supervisor'
import { STORAGE } from '../lib/settings'
import {
  loadToolkitCapabilityGates,
  toolkitGateBlocked,
  type ToolkitGateKey,
} from '../lib/toolkit-gates'
import {
  applyModifyHeaderRules,
  normalizeModifyHeaders,
} from '../lib/modify-headers'
import {
  openJsonFormatPage,
  openToolkitPage,
  ensureSidePanelRegistered,
  openSidePanelWithGesture,
  openSidePanelForStudioAttach,
  openSidePanelForTab,
  registerSidePanelForTab,
} from '../lib/surface-launch'
import {
  installContextMenus,
  registerContextMenuListeners,
} from '../lib/context-menu'
import {
  runToolkitPaletteAction,
  TAB_OPTIONAL_TOOLS,
  TOOLKIT_PALETTE_RUN,
} from '../lib/toolkit-palette-runner'
import {
  describeSavedShot,
  flashCommandFeedback,
  resolveToolkitTab,
  toolkitCaptureFullPage,
  toolkitCaptureVisible,
  toolkitOpenTranslate,
} from '../lib/toolkit-actions'
import { friendlyCaptureError } from '../lib/capture-full-page'
import { ensureContentScript, isToolkitRestrictedUrl } from '../lib/ensure-content-script'
import { showToolkitPaletteOnTab } from '../lib/toolkit-palette-open'
import { launchScreenshotStudio, SCREENSHOT_STUDIO_MESSAGE } from '../modules/screenshot-studio'
import {
  hideGeniusFallHudOnTab,
  HUD_MSG,
  openGeniusFallHudOnTab,
  refreshGeniusFallHudOnTab,
  saveHudPosition,
  saveHudPrefs,
  syncGeniusFallHudFollowActiveTab,
  toggleGeniusFallHudOnTab,
} from '../modules/genius-fall/hud-controller'
import {
  handleBehaviorRecordMessage,
  onRecordingTabNavigated,
} from '../modules/behavior-forge/recorder'
import {
  closeBehaviorRecordingHudGlobal,
  patchBehaviorRecordingHudGlobal,
  syncBehaviorRecordingHudOnTabUpdated,
} from '../modules/behavior-forge/recording-hud-controller'
import { BEHAVIOR_RECORD } from '../modules/behavior-forge/messages'
import { ensureLocalHelper, migrateStorageToWorkspace, workspaceRpc } from '../lib/local-workspace'
import { shouldCaptureSniffEvent } from '../lib/sniff-ingest'
import type { SniffIngestInput } from '../lib/sniff-ingest'
import {
  getSniffProject,
  ingestSniffEvents,
  listSniffApis,
  listSniffProjects,
  listSniffSamples,
  setSniffProjectStatus,
} from '../lib/sniff-store'
import { getSniffSession, startSniffSession, stopSniffSession } from '../lib/sniff-session'
import { installDownloadMonitor } from '../lib/download-monitor'

async function flushSniffTab(
  tabId: number,
  projectId: string
): Promise<{ apis: number; samples: number }> {
  const project = await getSniffProject(projectId)
  if (!project) return { apis: 0, samples: 0 }
  const events = listNetwork(tabId, { limit: 200 })
  const inputs: SniffIngestInput[] = []
  for (const event of events) {
    if (!shouldCaptureSniffEvent(event, project.origin)) continue
    let resBody = event.bodyPreview
    const stored = getNetworkBody(tabId, event.id)
    if (stored && stored.kind !== 'binary') resBody = stored.body
    inputs.push({
      eventId: event.id,
      method: event.method,
      url: event.url,
      status: event.status,
      mimeType: event.mimeType,
      resBody,
      ts: event.ts,
    })
  }
  return ingestSniffEvents(projectId, inputs)
}

function forwardPageControl(
  tabId: number,
  message: unknown,
  sendResponse: (r: unknown) => void
) {
  chrome.tabs.sendMessage(tabId, message, (response) => {
    if (chrome.runtime.lastError) {
      sendResponse({
        success: false,
        error:
          chrome.runtime.lastError.message +
          ' — 请刷新页面，或确认 Side Panel 焦点对应的是目标标签页。',
      })
      return
    }
    sendResponse(response)
  })
}

let captureInFlight = false

async function toolkitGateOrAbort(
  key: ToolkitGateKey,
  tabId?: number
): Promise<boolean> {
  const gates = await loadToolkitCapabilityGates()
  const blocked = toolkitGateBlocked(gates, key)
  if (!blocked) return true
  await flashCommandFeedback(blocked, tabId)
  return false
}

async function handleScreenshotStudio(tabId?: number): Promise<{ ok: boolean; error?: string }> {
  const tab = await resolveToolkitTab(tabId)
  const result = await launchScreenshotStudio(tab?.id)
  if (!result.ok && result.error) {
    await flashCommandFeedback(result.error, tab?.id)
  }
  return result
}

async function handleToolkitCapture(
  kind: 'visible' | 'fullpage',
  tabId?: number
): Promise<{ ok: boolean; error?: string; path?: string }> {
  const tab = await resolveToolkitTab(tabId)
  if (captureInFlight) {
    const busy = '正在截图，请稍候再试'
    await flashCommandFeedback(busy, tab?.id)
    return { ok: false, error: busy }
  }
  captureInFlight = true
  try {
    await flashCommandFeedback(
      {
        title: kind === 'fullpage' ? '正在拼全页截图…' : '正在截图…',
        hint: kind === 'fullpage' ? '长页面需要几秒，请不要连点' : '完成后会提示保存位置',
        ttlMs: 30_000,
      },
      tab?.id
    )
    // ponytail: popup steals the window; wait for it to close before captureVisibleTab. Raise if shots stay blank.
    await new Promise((resolve) => setTimeout(resolve, 150))
    const result = kind === 'fullpage' ? await toolkitCaptureFullPage(tab?.id) : await toolkitCaptureVisible(tab?.id)
    if (!result.ok) {
      const message = friendlyCaptureError(result.error ?? '截图失败')
      await flashCommandFeedback(message, tab?.id)
      await chrome.storage.local.set({
        [STORAGE.openWorkspaceDir]: 'shots',
        [STORAGE.openWorkspaceNotice]: message,
      })
      return { ...result, error: message }
    }
    const inDownloads = Boolean(result.downloadId) || Boolean(result.path?.startsWith('Downloads/'))
    const helper = inDownloads ? null : await ensureLocalHelper()
    const described = describeSavedShot(
      result.path ?? (kind === 'fullpage' ? '全页截图' : '可见截图'),
      helper?.ok ? helper.workspaceRoot : undefined
    )
    await flashCommandFeedback(
      {
        title: described.title,
        location: described.location,
        hint: described.hint,
        revealPath: described.inDownloads ? undefined : result.path,
        downloadId: result.downloadId,
      },
      tab?.id
    )
    await chrome.storage.local.set({
      [STORAGE.openWorkspaceDir]: 'shots',
      [STORAGE.openWorkspaceNotice]: `${described.title}：${described.location}`,
    })
    return result
  } catch (error) {
    const message = friendlyCaptureError((error as Error).message)
    await flashCommandFeedback(message, tab?.id)
    return { ok: false, error: message }
  } finally {
    captureInFlight = false
  }
}

export default defineBackground(() => {
  ensureNetworkListeners()
  installDownloadMonitor()
  ensureTabNetworkSessionListeners()
  startHostBridge()
  void ensureLocalHelper().then((helper) => {
    if (helper.ok) void migrateStorageToWorkspace()
  })
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false }).catch(() => {})
  void ensureSidePanelRegistered()
  chrome.tabs.onActivated.addListener(({ tabId }) => {
    registerSidePanelForTab(tabId)
    void syncGeniusFallHudFollowActiveTab(tabId)
  })
  chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
    if (changeInfo.status === 'complete') {
      registerSidePanelForTab(tabId)
      void onRecordingTabNavigated(tabId)
      void syncGeniusFallHudFollowActiveTab(tabId)
      void syncBehaviorRecordingHudOnTabUpdated(tabId)
    }
  })
  chrome.webNavigation.onHistoryStateUpdated.addListener((details) => {
    if (details.frameId !== 0) return
    void syncBehaviorRecordingHudOnTabUpdated(details.tabId)
  })
  void installContextMenus()
  registerContextMenuListeners()
  chrome.runtime.onInstalled.addListener(() => {
    void ensureSidePanelRegistered()
    void installContextMenus()
  })

  void chrome.storage.local.get(STORAGE.modifyHeaders).then((saved) => {
    void applyModifyHeaderRules(normalizeModifyHeaders(saved[STORAGE.modifyHeaders])).catch(() => {})
  })
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local' || !changes[STORAGE.modifyHeaders]) return
    void applyModifyHeaderRules(normalizeModifyHeaders(changes[STORAGE.modifyHeaders].newValue)).catch(
      () => {}
    )
  })

  chrome.runtime.onMessage.addListener((message, sender, sendResponse): true | undefined => {
    if (message?.type === SCREENSHOT_STUDIO_MESSAGE.launch) {
      const tabId = typeof message.tabId === 'number' ? message.tabId : sender.tab?.id
      void handleScreenshotStudio(tabId).then(sendResponse)
      return true
    }

    if (message?.type === SCREENSHOT_STUDIO_MESSAGE.openSidePanel) {
      const tabId =
        typeof message.tabId === 'number' ? message.tabId : sender.tab?.id
      const windowId =
        typeof message.windowId === 'number' ? message.windowId : sender.tab?.windowId
      if (tabId == null) {
        sendResponse({ ok: false, error: 'missing tab' })
        return true
      }
      const opened = openSidePanelWithGesture(tabId, windowId)
      sendResponse(opened.ok ? { ok: true } : { ok: false, error: opened.error })
      return true
    }

    if (message?.type === SCREENSHOT_STUDIO_MESSAGE.attach) {
      const tabId =
        typeof message.tabId === 'number' ? message.tabId : sender.tab?.id
      const windowId =
        typeof message.windowId === 'number' ? message.windowId : sender.tab?.windowId
      if (tabId != null) {
        openSidePanelForStudioAttach(tabId, windowId)
        void chrome.tabs.get(tabId).then((tab) => {
          if (tab?.id) void openSidePanelForTab(tab)
        })
      }
      sendResponse({ ok: true })
      return true
    }

    if (message?.type === 'TOOLKIT_OPEN_PALETTE') {
      const tabId = typeof message.tabId === 'number' ? message.tabId : sender.tab?.id
      if (!tabId) {
        sendResponse({ ok: false, error: '没有可用的网页标签' })
        return true
      }
      void showToolkitPaletteOnTab(tabId).then(sendResponse)
      return true
    }

    if (message?.type === TOOLKIT_PALETTE_RUN) {
      const tabId =
        typeof message.tabId === 'number' ? message.tabId : sender.tab?.id
      const toolId = message.toolId as import('../lib/toolkit-catalog').ToolkitCatalogId
      if (toolId === 'sidepanel' && tabId) {
        const opened = openSidePanelWithGesture(tabId, sender.tab?.windowId)
        sendResponse(opened.ok ? { ok: true } : { ok: false, error: opened.error })
        return true
      }
      if (!tabId && !TAB_OPTIONAL_TOOLS.has(toolId)) {
        sendResponse({ ok: false, error: '没有可用的网页标签' })
        return true
      }
      void runToolkitPaletteAction(toolId, tabId ?? 0).then(
        (result) => {
          sendResponse(result)
          if (!result.ok && !result.cancelled && result.error && tabId) {
            void flashCommandFeedback(result.error, tabId)
          }
        }
      )
      return true
    }

    if (message?.type === BEHAVIOR_RECORD) {
      void handleBehaviorRecordMessage(message as Record<string, unknown>, sender)
        .then(sendResponse)
        .catch((error) => {
          sendResponse({ ok: false, error: (error as Error).message ?? String(error) })
        })
      return true
    }

    if (message?.type === 'BEHAVIOR_RECORDING_HUD') {
      void (async () => {
        const action = String(message.action ?? '')
        if (action === 'open_replay') {
          const { openOptionsPage } = await import('../lib/surface-launch')
          await chrome.storage.local.set({ [STORAGE.openWorkspaceTab]: 'replay' })
          await openOptionsPage('workspace')
          sendResponse({ ok: true })
          return
        }
        if (action === 'close') {
          await closeBehaviorRecordingHudGlobal()
          sendResponse({ ok: true })
          return
        }
        if (action === 'save_pos') {
          if (typeof message.x === 'number' && typeof message.y === 'number') {
            await patchBehaviorRecordingHudGlobal({ posX: message.x, posY: message.y })
          }
          sendResponse({ ok: true })
          return
        }
        if (action === 'phase_update') {
          const phase = message.phase as import('../modules/behavior-forge/recording-hud.js').RecordingHudPhase | undefined
          await patchBehaviorRecordingHudGlobal({
            phase: phase ?? 'idle',
            savedCount:
              typeof message.savedCount === 'number' ? message.savedCount : message.savedCount === null ? null : undefined,
            error: typeof message.error === 'string' ? message.error : message.error === null ? undefined : undefined,
          })
          sendResponse({ ok: true })
          return
        }
        sendResponse({ ok: false, error: 'unknown action' })
      })()
      return true
    }

    if (message?.type === HUD_MSG) {
      const tabId =
        sender.tab?.id ?? (typeof message.tabId === 'number' ? message.tabId : undefined)
      void (async () => {
        const action = String(message.action ?? '')
        if (action === 'move' && typeof message.x === 'number' && typeof message.y === 'number') {
          await saveHudPosition(message.x, message.y)
          sendResponse({ ok: true })
          return
        }
        if (action === 'prefs' && message.prefs && typeof message.prefs === 'object') {
          const prefs = await saveHudPrefs(message.prefs as Record<string, unknown>)
          sendResponse({ ok: true, prefs })
          return
        }
        if (action === 'refresh' && tabId) {
          await refreshGeniusFallHudOnTab(tabId)
          sendResponse({ ok: true })
          return
        }
        if (action === 'open_panel') {
          const { openOptionsPageFromPopup } = await import('../lib/surface-launch')
          openOptionsPageFromPopup('geniusFall')
          sendResponse({ ok: true })
          return
        }
        if (action === 'toggle' && tabId) {
          try {
            const result = await toggleGeniusFallHudOnTab(tabId)
            sendResponse({ ok: true, ...result })
          } catch (error) {
            sendResponse({
              ok: false,
              error: error instanceof Error ? error.message : String(error),
            })
          }
          return
        }
        if (action === 'open' && tabId) {
          try {
            const result = await openGeniusFallHudOnTab(tabId)
            sendResponse({ ok: true, ...result })
          } catch (error) {
            sendResponse({
              ok: false,
              error: error instanceof Error ? error.message : String(error),
            })
          }
          return
        }
        if (action === 'close') {
          const { closeGeniusFallHudGlobal } = await import('../modules/genius-fall/hud-controller')
          await closeGeniusFallHudGlobal()
          sendResponse({ ok: true })
          return
        }
        sendResponse({ ok: false, error: 'unknown action' })
      })()
      return true
    }

    if (message?.type === 'TOOLKIT_CAPTURE') {
      const tabId = typeof message.tabId === 'number' ? message.tabId : undefined
      sendResponse({ ok: true, started: true })
      void handleToolkitCapture(message.kind === 'fullpage' ? 'fullpage' : 'visible', tabId).catch((error) => {
        void flashCommandFeedback(friendlyCaptureError((error as Error).message))
      })
      return
    }

    if (message?.type === 'WORKSPACE_REVEAL') {
      const path = typeof message.path === 'string' ? message.path : ''
      void workspaceRpc('open', { path }).catch((error) => {
        void flashCommandFeedback(`无法打开位置：${(error as Error).message}`)
      })
      sendResponse({ ok: true })
      return
    }

    if (message?.type === 'DOWNLOADS_SHOW') {
      const downloadId = message.downloadId
      if (typeof downloadId === 'number') chrome.downloads.show(downloadId)
      sendResponse({ ok: true })
      return
    }

    if (message?.type === 'PAGE_CONTROL') {
      if (message.action === 'get_my_tab_id') {
        sendResponse({ tabId: sender.tab?.id ?? null })
        return
      }
      if (message.action === 'ping' && sender.tab?.id != null) {
        // content → background ping unused; ignore
        return
      }

      const targetTabId = message.targetTabId as number | undefined
      if (!targetTabId) {
        sendResponse({ success: false, error: 'targetTabId required' })
        return
      }

      void (async () => {
        const ensured = await ensureContentScript(targetTabId)
        if (!ensured.ok) {
          sendResponse({ success: false, error: ensured.error })
          return
        }
        forwardPageControl(targetTabId, message, sendResponse)
      })()
      return true
    }

    if (message?.type === 'NETWORK') {
      void (async () => {
        try {
          const tabId = message.tabId as number
          switch (message.action) {
            case 'attach': {
              // Route every attach through the same recovery path used at run
              // start (retry + DevTools/foreign-debugger detection + tab
              // duplication). A bare attachNetwork() here would silently drop
              // all of that whenever Runtime re-attaches mid-run (e.g. after a
              // media candidate click), which previously surfaced as a
              // one-shot 'debugger attach failed' with no recovery attempted.
              const recovered = await attachNetworkWithRecovery(tabId, {
                captureBodies: message.captureBodies === true,
              })
              if (recovered.tabId !== tabId) {
                runSupervisor.retargetActiveRunTab(tabId, recovered.tabId)
              }
              sendResponse(
                recovered.attached
                  ? { ok: true, attached: true, tabId: recovered.tabId }
                  : {
                      ok: false,
                      error: `${recovered.error ?? 'debugger attach failed'} (${recovered.cause}; tried ${recovered.actions.join(', ') || 'none'})`,
                      tabId: recovered.tabId,
                    }
              )
              return
            }
            case 'probe': {
              const targets = await chrome.debugger.getTargets()
              const target = targets.find((item) => item.tabId === tabId)
              if (target?.attached) {
                const ours = !target.extensionId || target.extensionId === chrome.runtime.id
                sendResponse(
                  ours ? { ok: true } : { ok: false, error: 'debugger in use — close DevTools or other debuggers' }
                )
                return
              }
              const r = await attachNetwork(tabId)
              if (r.attached) await detachNetwork(tabId)
              sendResponse(r.attached ? { ok: true } : { ok: false, error: r.error })
              return
            }
            case 'detach': {
              await detachNetwork(tabId)
              sendResponse({ ok: true })
              return
            }
            case 'release_run': {
              await releaseRunNetwork(tabId)
              sendResponse({ ok: true })
              return
            }
            case 'bind_session': {
              const r = await bindToolkitTabNetwork(tabId)
              sendResponse(r.ok ? { ok: true } : { ok: false, error: r.error })
              return
            }
            case 'segment': {
              segmentNetworkTab(tabId, String(message.url ?? ''))
              sendResponse({ ok: true })
              return
            }
            case 'script_bodies': {
              sendResponse({
                ok: true,
                data: listScriptBodyPreviews(tabId, Number(message.limit ?? 6)),
              })
              return
            }
            case 'fetch_script_bodies': {
              const urls = Array.isArray(message.urls)
                ? message.urls.filter((u: unknown): u is string => typeof u === 'string')
                : []
              sendResponse({
                ok: true,
                data: await fetchMissingScriptBodies(tabId, urls, 4),
              })
              return
            }
            case 'digest': {
              if (!(await verifyNetworkDebuggerAttached(tabId))) {
                sendResponse({ ok: false, error: 'debugger not attached' })
                return
              }
              sendResponse({ ok: true, data: digestNetwork(tabId, message.limit ?? 12) })
              return
            }
            case 'list': {
              if (!(await verifyNetworkDebuggerAttached(tabId))) {
                sendResponse({ ok: false, error: 'debugger not attached' })
                return
              }
              sendResponse({ ok: true, data: listNetwork(tabId, message.filter) })
              return
            }
            case 'wait': {
              try {
                const hit = await waitNetwork(tabId, message.opts ?? {})
                if (!hit) {
                  sendResponse({ ok: false, error: 'timeout' })
                  return
                }
                sendResponse({ ok: true, data: hit })
              } catch (error) {
                if ((error as Error).name === 'AbortError') {
                  sendResponse({ ok: false, error: 'cancelled' })
                  return
                }
                sendResponse({ ok: false, error: (error as Error).message })
              }
              return
            }
            case 'cancelWaits': {
              cancelNetworkWaits(tabId)
              sendResponse({ ok: true })
              return
            }
            case 'clear': {
              clearNetwork(tabId)
              sendResponse({ ok: true })
              return
            }
            case 'setIntercepts': {
              const r = await setIntercepts(tabId, message.rules ?? [])
              if (r.error) sendResponse({ ok: false, error: r.error })
              else sendResponse({ ok: true, enabled: r.enabled, count: r.count })
              return
            }
            case 'listIntercepts': {
              sendResponse({ ok: true, data: listIntercepts(tabId) })
              return
            }
            case 'clearIntercepts': {
              await clearIntercepts(tabId)
              sendResponse({ ok: true })
              return
            }
            case 'getBody': {
              const body = getNetworkBody(tabId, String(message.id ?? ''))
              if (!body) sendResponse({ ok: false, error: 'body not found' })
              else sendResponse({ ok: true, data: body })
              return
            }
            default:
              sendResponse({ ok: false, error: 'unknown NETWORK action' })
          }
        } catch (e) {
          sendResponse({ ok: false, error: (e as Error).message })
        }
      })()
      return true
    }

    if (message?.type === 'SNIFF') {
      void (async () => {
        try {
          switch (message.action) {
            case 'status': {
              const tabId = message.tabId as number | undefined
              const session = tabId != null ? getSniffSession(tabId) : undefined
              const live =
                tabId != null ? listNetwork(tabId, { limit: 200 }).length : 0
              sendResponse({ ok: true, session, live })
              return
            }
            case 'start': {
              const projectId = String(message.projectId ?? '')
              const tabId = Number(message.tabId)
              if (!projectId || !tabId) {
                sendResponse({ ok: false, error: 'projectId and tabId required' })
                return
              }
              const attached = await attachNetwork(tabId, { captureBodies: true })
              if (!attached.attached) {
                sendResponse({ ok: false, error: attached.error ?? 'debugger attach failed' })
                return
              }
              startSniffSession(projectId, tabId)
              await setSniffProjectStatus(projectId, 'recording', tabId)
              sendResponse({ ok: true })
              return
            }
            case 'stop': {
              const tabId = Number(message.tabId)
              const projectId =
                stopSniffSession(tabId) ?? String(message.projectId ?? '')
              if (!projectId) {
                sendResponse({ ok: false, error: 'no active sniff session' })
                return
              }
              const ingested = await flushSniffTab(tabId, projectId)
              await setSniffProjectStatus(projectId, 'idle')
              sendResponse({ ok: true, data: ingested })
              return
            }
            case 'flush': {
              const tabId = Number(message.tabId)
              const projectId = String(message.projectId ?? '')
              const ingested = await flushSniffTab(tabId, projectId)
              sendResponse({ ok: true, data: ingested })
              return
            }
            case 'listProjects': {
              sendResponse({ ok: true, data: await listSniffProjects() })
              return
            }
            case 'listApis': {
              sendResponse({
                ok: true,
                data: await listSniffApis(String(message.projectId ?? '')),
              })
              return
            }
            case 'listSamples': {
              sendResponse({
                ok: true,
                data: await listSniffSamples(String(message.apiId ?? '')),
              })
              return
            }
            default:
              sendResponse({ ok: false, error: 'unknown SNIFF action' })
          }
        } catch (error) {
          sendResponse({ ok: false, error: (error as Error).message })
        }
      })()
      return true
    }

    if (message?.type === 'AGENT_RUN') {
      const result = runSupervisor.dispatch(message)
      if (result.async) {
        chrome.storage.local.remove(STORAGE.activeRun).then(() => {
          sendResponse({ ok: true, active: false })
        })
        return true
      }
      if (result.response) {
        sendResponse(result.response)
        return
      }
      sendResponse(result.ok ? { ok: true } : { ok: false, error: result.error })
      return
    }

    return
  })
})

try {
  chrome.commands.onCommand.addListener((command) => {
    void (async () => {
      try {
        if (command === 'open-toolkit') {
          await openToolkitPage()
          return
        }
        if (command === 'open-json-format') {
          await openJsonFormatPage()
          return
        }
        if (command === 'capture-full-page') {
          const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
          await handleToolkitCapture('fullpage', tab?.id)
          return
        }
        if (command === 'capture-visible') {
          const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
          await handleToolkitCapture('visible', tab?.id)
          return
        }
        if (command === 'screenshot-studio') {
          const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
          await handleScreenshotStudio(tab?.id)
          return
        }
        if (command === 'toolkit-translate') {
          const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
          if (!tab?.id || isToolkitRestrictedUrl(tab.url)) {
            await flashCommandFeedback('请先打开一个普通网页')
            return
          }
          if (!(await toolkitGateOrAbort('allowDomInject', tab.id))) return
          await toolkitOpenTranslate(tab)
        }
      } catch (error) {
        await flashCommandFeedback(friendlyCaptureError((error as Error).message))
      }
    })()
  })
} catch {
  // wxt build uses a fake browser without commands API
}
