import { openOptionsPage, openPageToolList, openSidePanelFromPopupClick } from './surface-launch'
import { pinCurrentWebTab } from './toolkit-actions'
import { openGeniusFallHudOnTab, resolveGeniusFallHudTab } from '../modules/genius-fall/hud-controller'
import { toggleBehaviorRecording } from './behavior-recording-actions'
import type { ToolkitCatalogId } from './toolkit-catalog'
import {
  runToolkitPaletteAction,
  TAB_OPTIONAL_TOOLS,
  TOOLKIT_PALETTE_RUN,
} from './toolkit-palette-runner'

export async function runPopupTool(
  toolId: ToolkitCatalogId
): Promise<{ ok: boolean; error?: string; cancelled?: boolean }> {
  if (toolId === 'sidepanel') {
    openSidePanelFromPopupClick()
    return { ok: true }
  }
  if (toolId === 'page-toollist') {
    return await openPageToolList()
  }
  if (toolId === 'settings') {
    await openOptionsPage('settings')
    return { ok: true }
  }
  if (toolId === 'account') {
    await openOptionsPage('account')
    return { ok: true }
  }
  if (toolId === 'genius-fall') {
    const tab = await pinCurrentWebTab()
    const tabId = tab?.id ?? (await resolveGeniusFallHudTab())
    if (!tabId) return { ok: false, error: '请先打开一个普通网页' }
    try {
      const result = (await chrome.runtime.sendMessage({
        type: 'GENIUS_FALL_HUD',
        action: 'open',
        tabId,
      })) as { ok?: boolean; error?: string } | undefined
      if (!result || result.ok === false) {
        return { ok: false, error: result?.error ?? '扩展未响应，请刷新当前页面后重试' }
      }
      return { ok: true }
    } catch (error) {
      return {
        ok: false,
        error: error instanceof Error ? error.message : '无法打开 Token 监控',
      }
    }
  }
  if (toolId === 'behavior-forge') {
    const tab = await pinCurrentWebTab()
    const result = await toggleBehaviorRecording(tab?.id)
    if (!result.ok) {
      return {
        ok: false,
        error: result.error === 'need_tab' ? '请先打开一个普通网页' : result.error,
      }
    }
    return { ok: true }
  }

  const tab = await pinCurrentWebTab()
  const tabId = tab?.id

  if (!tabId && !TAB_OPTIONAL_TOOLS.has(toolId)) {
    return { ok: false, error: '请先打开一个普通网页' }
  }

  if (tabId != null) {
    const result = (await chrome.runtime.sendMessage({
      type: TOOLKIT_PALETTE_RUN,
      toolId,
      tabId,
    })) as { ok?: boolean; error?: string; cancelled?: boolean } | undefined
    if (result?.cancelled) return { ok: true, cancelled: true }
    if (result && result.ok === false && result.error) return { ok: false, error: result.error }
    return { ok: true }
  }

  return await runToolkitPaletteAction(toolId, 0)
}
