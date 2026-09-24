import { STORAGE } from './settings'
import { flashCommandFeedback, setPinnedToolkitTabId } from './toolkit-actions'
import { openPageToolList, openSidePanelWithGesture, openWorkspaceTab } from './surface-launch'

export const CONTEXT_MENU = {
  openAgent: 'naviforge-open-agent',
  askSelection: 'naviforge-ask-selection',
  more: 'naviforge-more',
  workspace: 'naviforge-workspace',
  tools: 'naviforge-tools',
} as const

export type ContextMenuActionId = (typeof CONTEXT_MENU)[keyof typeof CONTEXT_MENU]

export function isContextMenuAction(id: string | number): id is ContextMenuActionId {
  return Object.values(CONTEXT_MENU).includes(id as ContextMenuActionId)
}

let menuInstall: Promise<void> = Promise.resolve()

export async function installContextMenus(): Promise<void> {
  if (!chrome.contextMenus?.create) return
  menuInstall = menuInstall.then(async () => {
    await chrome.contextMenus.removeAll()
    const title = (key: string, fallback: string) => chrome.i18n.getMessage(key) || fallback

  chrome.contextMenus.create({
    id: CONTEXT_MENU.openAgent,
    title: title('contextOpenAgent', 'Open NaviForge Agent'),
    contexts: ['page', 'frame', 'editable'],
  })

  chrome.contextMenus.create({
    id: CONTEXT_MENU.askSelection,
    title: title('contextAskSelection', 'Ask NaviForge about selection'),
    contexts: ['selection'],
  })

  chrome.contextMenus.create({
    id: CONTEXT_MENU.more,
    title: title('contextMore', 'NaviForge'),
    contexts: ['page', 'frame', 'selection', 'editable'],
  })

  chrome.contextMenus.create({
    id: CONTEXT_MENU.workspace,
    parentId: CONTEXT_MENU.more,
    title: title('contextOpenWorkspace', 'Open workspace'),
    contexts: ['page', 'frame', 'selection', 'editable'],
  })

  chrome.contextMenus.create({
    id: CONTEXT_MENU.tools,
    parentId: CONTEXT_MENU.more,
    title: title('contextOpenTools', 'Tool list'),
    contexts: ['page', 'frame', 'selection', 'editable'],
  })
  })
  return menuInstall
}

async function resolveContextTab(tab?: chrome.tabs.Tab): Promise<chrome.tabs.Tab | null> {
  if (tab?.id != null) return tab
  const [active] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  return active?.id != null ? active : null
}

export async function openAgentForTab(
  tabId: number,
  opts?: { selection?: string }
): Promise<{ ok: true } | { ok: false; error: string }> {
  const tab = await chrome.tabs.get(tabId)
  if (tab.id != null) await setPinnedToolkitTabId(tab.id)
  const selection = opts?.selection?.trim()
  if (selection) {
    await chrome.storage.local.set({
      [STORAGE.resumeSession]: {
        task: selection,
        page:
          tab.id != null
            ? { tabId: tab.id, url: tab.url, title: tab.title }
            : undefined,
      },
    })
  }
  return { ok: true }
}

export async function handleContextMenuClick(
  info: chrome.contextMenus.OnClickData,
  tab?: chrome.tabs.Tab,
  opts?: { sidePanelOpened?: boolean }
): Promise<void> {
  const target = await resolveContextTab(tab)
  const tabId = target?.id
  if (!tabId || !target) return
  if (!isContextMenuAction(info.menuItemId)) return

  if (info.menuItemId === CONTEXT_MENU.openAgent) {
    if (!opts?.sidePanelOpened) {
      const opened = openSidePanelWithGesture(tabId, target.windowId)
      if (!opened.ok) {
        await flashCommandFeedback(`无法打开 Agent 侧栏：${opened.error}`, tabId)
        return
      }
    }
    await openAgentForTab(tabId)
    return
  }
  if (info.menuItemId === CONTEXT_MENU.askSelection) {
    if (!opts?.sidePanelOpened) {
      const opened = openSidePanelWithGesture(tabId, target.windowId)
      if (!opened.ok) {
        await flashCommandFeedback(`无法打开 Agent 侧栏：${opened.error}`, tabId)
        return
      }
    }
    const result = await openAgentForTab(tabId, { selection: info.selectionText })
    if (!result.ok) await flashCommandFeedback(`无法打开 Agent 侧栏：${result.error}`, tabId)
    return
  }
  if (info.menuItemId === CONTEXT_MENU.workspace) {
    await openWorkspaceTab(tabId)
    return
  }
  if (info.menuItemId === CONTEXT_MENU.tools) {
    if (target.id != null) await setPinnedToolkitTabId(target.id)
    const listed = await openPageToolList()
    if (!listed.ok && listed.error) await flashCommandFeedback(listed.error, tabId)
  }
}

export function registerContextMenuListeners(): void {
  if (!chrome.contextMenus?.onClicked) return
  chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (!isContextMenuAction(info.menuItemId)) return

    const opensAgent =
      info.menuItemId === CONTEXT_MENU.openAgent ||
      info.menuItemId === CONTEXT_MENU.askSelection
    let sidePanelOpened = false
    if (opensAgent && tab?.id != null) {
      const opened = openSidePanelWithGesture(tab.id, tab.windowId)
      sidePanelOpened = opened.ok
      if (!opened.ok) {
        void flashCommandFeedback(`无法打开 Agent 侧栏：${opened.error}`, tab.id)
        return
      }
    }

    void handleContextMenuClick(info, tab, { sidePanelOpened })
  })
}
