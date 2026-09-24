import { friendlyCaptureError } from './capture-full-page'
import { lookupPublicIp } from './net-diag'
import { formatTranslationFeedback } from './page-translate'
import { openJsonFormatPage, openToolkitPage, openToolkitPageWithRunResult, openWorkspaceTab } from './surface-launch'
import {
  flashCommandFeedback,
  flashSavedShotFeedback,
  toolkitCaptureFullPage,
  toolkitCaptureVisible,
  toolkitExtract,
  toolkitMarkTopn,
  toolkitOpenTranslate,
} from './toolkit-actions'
import { toolkitToggleVideoSubtitles } from './video-subtitles'
import { runToolkitOcr } from './vision-ocr'
import { toggleGeniusFallHudOnTab } from '../modules/genius-fall/hud-controller'
import type { ToolkitCatalogId } from './toolkit-catalog'

/** Tools that can run without an active web tab (popup · background palette). */
export const TAB_OPTIONAL_TOOLS: ReadonlySet<ToolkitCatalogId> = new Set([
  'workspace',
  'sidepanel',
  'json',
  'myip',
  'toolkit-admin',
  'settings',
  'account',
])

export async function runToolkitPaletteAction(
  toolId: ToolkitCatalogId,
  tabId: number
): Promise<{ ok: boolean; error?: string; cancelled?: boolean }> {
  const tab =
    tabId > 0
      ? await chrome.tabs.get(tabId).catch(() => null)
      : null
  if (!tab && !TAB_OPTIONAL_TOOLS.has(toolId)) {
    return { ok: false, error: '没有可用的网页标签' }
  }
  try {
    switch (toolId) {
      case 'page-toollist': {
        const { openPageToolList } = await import('./surface-launch')
        return await openPageToolList()
      }
      case 'sidepanel': {
        if (!tab?.id) return { ok: false, error: '没有可用的网页标签' }
        const { openSidePanelWithGesture } = await import('./surface-launch')
        return openSidePanelWithGesture(tab.id, tab.windowId)
      }
      case 'settings': {
        const { openOptionsPage } = await import('./surface-launch')
        await openOptionsPage('settings')
        return { ok: true }
      }
      case 'account': {
        const { openOptionsPage } = await import('./surface-launch')
        await openOptionsPage('account')
        return { ok: true }
      }
      case 'workspace':
        await openWorkspaceTab()
        return { ok: true }
      case 'studio': {
        const result = await launchScreenshotStudio(tabId)
        return result
      }
      case 'screenshot': {
        const result = await toolkitCaptureVisible(tabId)
        if (!result.ok) return { ok: false, error: result.error ?? '截图失败' }
        await flashSavedShotFeedback(tabId, result, '可见截图已保存')
        return { ok: true }
      }
      case 'fullpage': {
        const result = await toolkitCaptureFullPage(tabId)
        if (!result.ok) return { ok: false, error: result.error ?? '全页截图失败' }
        await flashSavedShotFeedback(tabId, result, '全页截图已保存')
        return { ok: true }
      }
      case 'extract': {
        const extracted = await toolkitExtract(tabId, 10)
        if (!extracted.ok) return { ok: false, error: extracted.error.message }
        const count = extracted.data.items.length
        await openToolkitPageWithRunResult({
          kind: 'list',
          title: `提取 ${count} 条`,
          target: tab?.url,
          elapsedMs: 0,
          items: extracted.data.items,
          meta: extracted.data.strategy ?? undefined,
        })
        await flashCommandFeedback(
          {
            title: `已提取 ${count} 条`,
            hint: '右侧结果抽屉已打开（控制台 → 工具）',
            ttlMs: 6000,
          },
          tabId
        )
        return { ok: true }
      }
      case 'mark': {
        const marked = await toolkitMarkTopn(tabId, 10)
        if (!marked.ok) return { ok: false, error: marked.error.message }
        await flashCommandFeedback(`已在页面标记 ${marked.data.marked} 条`, tabId)
        return { ok: true }
      }
      case 'translate': {
        const opened = await toolkitOpenTranslate(tab!)
        if (!opened.ok) return { ok: false, error: opened.error ?? '翻译失败' }
        await flashCommandFeedback(formatTranslationFeedback(opened), tabId)
        return { ok: true }
      }
      case 'subs': {
        const toggled = await toolkitToggleVideoSubtitles(tab!)
        if (!toggled.ok) return { ok: false, error: toggled.error ?? '字幕失败' }
        await flashCommandFeedback(toggled.message ?? '字幕已切换', tabId)
        return { ok: true }
      }
      case 'genius-fall': {
        const { resolveGeniusFallHudTab, toggleGeniusFallHudOnTab } = await import(
          '../modules/genius-fall/hud-controller'
        )
        const id = tabId > 0 ? tabId : await resolveGeniusFallHudTab()
        if (!id) return { ok: false, error: '没有可用的网页标签' }
        const { visible } = await toggleGeniusFallHudOnTab(id)
        await flashCommandFeedback(
          visible ? '天才陨落已显示 · 可拖动' : '天才陨落已关闭',
          id
        )
        return { ok: true }
      }
      case 'behavior-forge': {
        if (!tabId) return { ok: false, error: '没有可用的网页标签' }
        const { openBehaviorRecordingHud } = await import('./behavior-recording-actions')
        const opened = await openBehaviorRecordingHud(tabId)
        if (!opened.ok) return { ok: false, error: opened.error ?? '无法打开录制控制台' }
        return { ok: true }
      }
      case 'ocr': {
        const ocr = await runToolkitOcr(tab!)
        if ('cancelled' in ocr) return { ok: true, cancelled: true }
        if (ocr.path) {
          await flashSavedShotFeedback(tabId, { path: ocr.path }, 'OCR 识别完成')
        } else {
          await flashCommandFeedback(
            { title: 'OCR 识别完成', hint: '文字已显示在页面浮层', ttlMs: 8000 },
            tabId
          )
        }
        return { ok: true }
      }
      case 'json':
        await openJsonFormatPage()
        return { ok: true }
      case 'myip': {
        const info = await lookupPublicIp()
        const location = [info.city, info.region, info.country].filter(Boolean).join(' · ')
        if (tabId > 0) {
          await flashCommandFeedback(
            {
              title: '出口 IP',
              location: info.ip,
              hint: location || info.isp || info.organization || '详情见管理后台',
            },
            tabId
          )
        }
        return { ok: true }
      }
      case 'toolkit-admin':
        await openToolkitPage()
        return { ok: true }
      default:
        return { ok: false, error: `未知工具：${toolId}` }
    }
  } catch (error) {
    return { ok: false, error: friendlyCaptureError((error as Error).message) }
  }
}

export const TOOLKIT_PALETTE_RUN = 'TOOLKIT_PALETTE_RUN'
