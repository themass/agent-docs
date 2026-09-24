import type { TabSummary, TabsPlane } from '@naviforge/runtime'
import type { ToolResult } from '@naviforge/shared'

function restricted(url: string | undefined): boolean {
  if (!url) return true
  return (
    url.startsWith('chrome://') ||
    url.startsWith('chrome-extension://') ||
    url.startsWith('devtools://') ||
    url.startsWith('edge://') ||
    url.startsWith('about:')
  )
}

export function createChromeTabsPlane(opts: {
  getActiveTabId: () => number | null
  onSwitch: (tabId: number, tab: chrome.tabs.Tab) => void
}): TabsPlane {
  return createTabsPlaneCore({
    getActiveTabId: opts.getActiveTabId,
    onOpen: (tab) => opts.onSwitch(tab.id!, tab),
    onSwitch: (tabId, tab) => opts.onSwitch(tabId, tab),
    activateOnOpen: true,
    activateOnSwitch: true,
  })
}

/** Ephemeral tab scope for readonly leaf agents — never steals the parent anchor tab. */
export function createEphemeralTabScope(anchorTabId: number): {
  getActiveTabId: () => number
  tabs: TabsPlane
  dispose: () => Promise<void>
} {
  let activeTabId = anchorTabId
  const opened = new Set<number>()
  const tabs = createTabsPlaneCore({
    getActiveTabId: () => activeTabId,
    onOpen: (tab) => {
      if (tab.id) {
        opened.add(tab.id)
        activeTabId = tab.id
      }
    },
    onSwitch: (tabId) => {
      activeTabId = tabId
    },
    activateOnOpen: false,
    activateOnSwitch: false,
  })
  return {
    getActiveTabId: () => activeTabId,
    tabs,
    dispose: async () => {
      for (const tabId of [...opened]) {
        await chrome.tabs.remove(tabId).catch(() => {})
      }
      opened.clear()
      activeTabId = anchorTabId
    },
  }
}

function createTabsPlaneCore(opts: {
  getActiveTabId: () => number | null
  onOpen: (tab: chrome.tabs.Tab) => void
  onSwitch: (tabId: number, tab: chrome.tabs.Tab) => void
  activateOnOpen: boolean
  activateOnSwitch: boolean
}): TabsPlane {
  return {
    async list(): Promise<ToolResult<{ tabs: TabSummary[] }>> {
      try {
        const tabs = await chrome.tabs.query({})
        return {
          ok: true,
          data: {
            tabs: tabs
              .filter((tab) => tab.id != null && !restricted(tab.url))
              .map((tab) => ({
                id: tab.id!,
                url: tab.url,
                title: tab.title,
                active: tab.active === true,
                windowId: tab.windowId,
              })),
          },
        }
      } catch (error) {
        return {
          ok: false,
          error: { code: 'tabs_list_failed', message: (error as Error).message, recoverable: true },
        }
      }
    },

    async switch(tabId: number): Promise<ToolResult<{ tabId: number }>> {
      try {
        const tab = await chrome.tabs.update(tabId, { active: opts.activateOnSwitch })
        if (!tab?.id) {
          return {
            ok: false,
            error: { code: 'tabs_switch_failed', message: 'tab not found', recoverable: true },
          }
        }
        if (opts.activateOnSwitch && tab.windowId != null) {
          await chrome.windows.update(tab.windowId, { focused: true })
        }
        opts.onSwitch(tab.id, tab)
        return { ok: true, data: { tabId: tab.id } }
      } catch (error) {
        return {
          ok: false,
          error: { code: 'tabs_switch_failed', message: (error as Error).message, recoverable: true },
        }
      }
    },

    async close(tabId: number): Promise<ToolResult<{ closed: number }>> {
      try {
        const active = opts.getActiveTabId()
        await chrome.tabs.remove(tabId)
        if (active === tabId) {
          const [next] = await chrome.tabs.query({ active: true, currentWindow: true })
          if (next?.id) {
            const tab = await chrome.tabs.get(next.id)
            opts.onSwitch(next.id, tab)
          }
        }
        return { ok: true, data: { closed: tabId } }
      } catch (error) {
        return {
          ok: false,
          error: { code: 'tabs_close_failed', message: (error as Error).message, recoverable: true },
        }
      }
    },

    async open(url: string): Promise<ToolResult<{ tabId: number }>> {
      try {
        const tab = await chrome.tabs.create({ url, active: opts.activateOnOpen })
        if (!tab?.id) {
          return {
            ok: false,
            error: { code: 'tabs_open_failed', message: 'create tab failed', recoverable: true },
          }
        }
        opts.onOpen(tab)
        return { ok: true, data: { tabId: tab.id } }
      } catch (error) {
        return {
          ok: false,
          error: { code: 'tabs_open_failed', message: (error as Error).message, recoverable: true },
        }
      }
    },
  }
}
