import type { MutableRefObject } from 'react'

import { isToolkitPageUrl, listToolkitTabs, resolveToolkitTab } from '../lib/toolkit-actions'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'
import { adoptToolkitTab } from './workspace-restore'
import type { PickedElement, TopVideo } from './workspace-helpers'
import { pickedLabel } from './workspace-helpers'

export type TabControlDeps = {
  tabRef: MutableRefObject<number | null>
  runningRef: MutableRefObject<boolean>
  explainAfterPickRef: MutableRefObject<boolean>
  setTargetTab(value: {
    id: number
    url?: string
    title?: string
    windowId?: number
  } | null): void
  setPickingElement(value: boolean): void
  setPickedElement(value: PickedElement | null): void
  setTask(updater: (current: string) => string): void
  setAllTabs(
    value: Array<{ id: number; title?: string; url?: string; active: boolean; windowId?: number }>
  ): void
  setTabPickerOpen(value: boolean): void
  setRunOutcome(value: {
    kind: 'success' | 'failed' | 'blocked' | 'waiting' | 'cancelled'
    title: string
    message: string
  } | null): void
  push(line: string): void
}

export function createTabControl(deps: TabControlDeps) {
  function adoptTab(tab: chrome.tabs.Tab): void {
    adoptToolkitTab(tab, deps.tabRef, deps.setTargetTab)
  }

  async function bindActiveTab(): Promise<chrome.tabs.Tab | null> {
    if (deps.runningRef.current && deps.tabRef.current != null) {
      try {
        return await chrome.tabs.get(deps.tabRef.current)
      } catch {
        deps.push('✗ 锁定的控制标签已关闭')
        return null
      }
    }
    if (deps.tabRef.current != null) {
      try {
        const bound = await chrome.tabs.get(deps.tabRef.current)
        if (bound.id != null && isToolkitPageUrl(bound.url)) return bound
      } catch {
        deps.tabRef.current = null
      }
    }
    const [active] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (active?.id && isToolkitPageUrl(active.url)) {
      adoptTab(active)
      return active
    }
    const resolved = await resolveToolkitTab()
    if (resolved?.id) {
      adoptTab(resolved)
      return resolved
    }
    deps.push('✗ 请先打开一个普通网页标签')
    return null
  }

  async function getControlledTab(): Promise<chrome.tabs.Tab | null> {
    if (deps.tabRef.current != null) {
      try {
        return await chrome.tabs.get(deps.tabRef.current)
      } catch {
        deps.tabRef.current = null
      }
    }
    return bindActiveTab()
  }

  async function pickElement(): Promise<void> {
    if (deps.runningRef.current) {
      deps.push('运行中已锁定控制标签，请先停止 Agent')
      return
    }
    const tab = await getControlledTab()
    if (!tab?.id) {
      deps.push('✗ 没有可控制的标签页')
      return
    }
    try {
      await chrome.tabs.update(tab.id, { active: true })
      if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true })
      const result = (await safeRuntimeSendMessage({
        type: 'PAGE_CONTROL',
        action: 'pick_element',
        targetTabId: tab.id,
      })) as { success?: boolean; error?: string } | undefined
      if (!result?.success) {
        deps.setPickingElement(false)
        deps.explainAfterPickRef.current = false
        const message = result?.error ?? '请刷新网页后再试'
        deps.setRunOutcome({ kind: 'failed', title: '无法点选页面', message })
        return
      }
      deps.setPickingElement(true)
      deps.setPickedElement(null)
    } catch (error) {
      deps.setPickingElement(false)
      deps.explainAfterPickRef.current = false
      deps.setRunOutcome({
        kind: 'failed',
        title: '无法点选页面',
        message: `${(error as Error).message}。请刷新当前网页后再试。`,
      })
    }
  }

  function clearPickedElement(): void {
    deps.setPickedElement(null)
    deps.setPickingElement(false)
  }

  async function focusMarkedVideo(video: TopVideo): Promise<void> {
    const tabId = deps.tabRef.current
    if (!tabId) return
    try {
      const result = (await chrome.tabs.sendMessage(tabId, {
        type: 'PAGE_CONTROL',
        action: 'focus_mark',
        payload: { label: video.label },
      })) as { success?: boolean; error?: string }
      if (!result.success) deps.push(`✗ 无法定位 ${video.label}: ${result.error ?? '标记已失效'}`)
    } catch (error) {
      deps.push(`✗ 无法定位 ${video.label}: ${(error as Error).message}`)
    }
  }

  async function openTabPicker(): Promise<void> {
    if (deps.runningRef.current) {
      deps.setRunOutcome({
        kind: 'blocked',
        title: '无法切换标签',
        message: '运行中已锁定控制标签，请先停止 Agent',
      })
      return
    }
    try {
      const tabs = await listToolkitTabs()
      deps.setAllTabs(
        tabs.map((tab) => ({
          id: tab.id,
          title: tab.title,
          url: tab.url,
          active: tab.active === true,
          windowId: tab.windowId,
        }))
      )
      deps.setTabPickerOpen(true)
    } catch (error) {
      deps.setRunOutcome({
        kind: 'failed',
        title: '无法切换标签',
        message: (error as Error).message,
      })
    }
  }

  async function switchToTab(tabId: number, windowId?: number): Promise<void> {
    if (deps.runningRef.current) {
      deps.push('运行中已锁定控制标签，请先停止 Agent')
      return
    }
    await chrome.tabs.update(tabId, { active: true })
    if (windowId != null) await chrome.windows.update(windowId, { focused: true })
    const tab = await chrome.tabs.get(tabId)
    if (!isToolkitPageUrl(tab.url)) {
      deps.push('✗ 不能绑定扩展页或浏览器内部页')
      return
    }
    adoptTab(tab)
    deps.setTabPickerOpen(false)
    deps.push(`switched to tab #${tab.id} (window ${tab.windowId ?? '?'})`)
  }

  return {
    adoptTab,
    getControlledTab,
    pickElement,
    clearPickedElement,
    bindActiveTab,
    focusMarkedVideo,
    openTabPicker,
    switchToTab,
  }
}
