import type { MutableRefObject } from 'react'
import type { WorkspaceEntry } from '@naviforge/runtime'

import { createChromeDomPlane } from '../lib/chrome-dom-plane'
import {
  IMAGE_FILE_RE,
  isAllowedImageFile,
  MAX_IMAGE_BYTES,
} from '../lib/image-ask'
import { saveWorkspaceAudio, workspaceRpc } from '../lib/local-workspace'
import type { VoiceClip } from '../lib/audio-record'
import { setShotThumbsAvailable, shotThumbsAvailable } from './workspace-helpers'
import { SCREENSHOT_STUDIO_MESSAGE } from '../modules/screenshot-studio/messages.js'

export type AttachmentActionsDeps = {
  pageAskBusy: boolean
  runningRef: MutableRefObject<boolean>
  voiceRef: MutableRefObject<{ dataUrl: string; path?: string; label: string } | null>
  setRecentShots(value: Array<{ path: string; name: string; thumb?: string }>): void
  setImageAttachment(value: { dataUrl: string; label: string } | null): void
  setVoiceAttachment(value: { dataUrl: string; path?: string; label: string } | null): void
  setRunOutcome(value: {
    kind: 'success' | 'failed' | 'blocked' | 'waiting' | 'cancelled'
    title: string
    message: string
  } | null): void
  bindActiveTab(): Promise<chrome.tabs.Tab | null>
}

export function createAttachmentActions(deps: AttachmentActionsDeps) {
  async function refreshRecentShots(): Promise<void> {
    try {
      const { entries } = await workspaceRpc<{ entries: WorkspaceEntry[] }>('list', { dir: 'shots' })
      const listed = entries
        .filter((entry) => entry.kind === 'file' && IMAGE_FILE_RE.test(entry.name))
        .slice(-8)
        .reverse()
        .map((entry) => ({ path: `shots/${entry.name}`, name: entry.name }))
      deps.setRecentShots(listed)
      if (!listed.length || shotThumbsAvailable === false) return
      const withThumbs = await Promise.all(
        listed.map(async (shot) => {
          try {
            const { dataUrl } = await workspaceRpc<{ dataUrl: string }>('readDataUrl', { path: shot.path })
            setShotThumbsAvailable(true)
            return { ...shot, thumb: dataUrl }
          } catch (error) {
            if (/Host 版本过旧|unknown workspace op/i.test((error as Error).message)) {
              setShotThumbsAvailable(false)
            }
            return shot
          }
        })
      )
      deps.setRecentShots(withThumbs)
    } catch {
      deps.setRecentShots([])
    }
  }

  async function attachViewport(): Promise<void> {
    if (deps.pageAskBusy || deps.runningRef.current) {
      deps.setRunOutcome({ kind: 'blocked', title: '无法截图', message: '请等当前任务结束后再附图' })
      return
    }
    const tab = await deps.bindActiveTab()
    if (!tab?.id) {
      deps.setRunOutcome({ kind: 'failed', title: '无法截图', message: '请先绑定一个普通网页标签' })
      return
    }
    const dom = createChromeDomPlane(() => tab.id!)
    if (!dom.screenshot) {
      deps.setRunOutcome({ kind: 'failed', title: '无法截图', message: '当前环境不支持截图' })
      return
    }
    const shot = await dom.screenshot()
    if (!shot.ok || !shot.data?.dataUrl) {
      deps.setRunOutcome({
        kind: 'failed',
        title: '无法截图',
        message: shot.ok ? '截图失败' : shot.error.message,
      })
      return
    }
    deps.setImageAttachment({ dataUrl: shot.data.dataUrl, label: '当前可见区域' })
  }

  async function attachShot(path: string): Promise<void> {
    if (deps.pageAskBusy || deps.runningRef.current) return
    try {
      const { dataUrl } = await workspaceRpc<{ dataUrl: string }>('readDataUrl', { path })
      deps.setImageAttachment({ dataUrl, label: path })
    } catch (error) {
      deps.setRunOutcome({ kind: 'failed', title: '无法读取截图', message: (error as Error).message })
    }
  }

  async function attachFile(file: File): Promise<void> {
    if (deps.pageAskBusy || deps.runningRef.current) return
    if (!isAllowedImageFile(file)) {
      deps.setRunOutcome({
        kind: 'failed',
        title: '无法附加图片',
        message: file.size > MAX_IMAGE_BYTES ? '图片超过 8MB' : '仅支持 png / jpeg / webp / gif',
      })
      return
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result ?? ''))
      reader.onerror = () => reject(new Error('读取文件失败'))
      reader.readAsDataURL(file)
    })
    if (!dataUrl.startsWith('data:image/') || dataUrl.startsWith('data:image/svg')) {
      deps.setRunOutcome({ kind: 'failed', title: '无法附加图片', message: '仅支持 png / jpeg / webp / gif' })
      return
    }
    deps.setImageAttachment({ dataUrl, label: file.name })
  }

  async function attachVoice(clip: VoiceClip): Promise<void> {
    const saved = await saveWorkspaceAudio({ kind: 'voice', dataUrl: clip.dataUrl })
    const next = {
      dataUrl: clip.dataUrl,
      path: saved?.relativePath,
      label: saved?.relativePath ?? '语音',
    }
    deps.voiceRef.current = next
    deps.setVoiceAttachment(next)
  }

  function clearVoice(): void {
    deps.voiceRef.current = null
    deps.setVoiceAttachment(null)
  }

  async function launchScreenshotStudio(): Promise<void> {
    if (deps.pageAskBusy || deps.runningRef.current) {
      deps.setRunOutcome({
        kind: 'blocked',
        title: '无法截图',
        message: '请等当前任务结束后再使用截图工作室',
      })
      return
    }
    const tab = await deps.bindActiveTab()
    const result = (await chrome.runtime.sendMessage({
      type: SCREENSHOT_STUDIO_MESSAGE.launch,
      tabId: tab?.id,
    })) as { ok?: boolean; cancelled?: boolean; error?: string }
    if (result?.cancelled) return
    if (result && result.ok === false && result.error) {
      deps.setRunOutcome({ kind: 'failed', title: '截图工作室', message: result.error })
    }
  }

  return {
    refreshRecentShots,
    attachViewport,
    attachShot,
    attachFile,
    attachVoice,
    clearVoice,
    launchScreenshotStudio,
  }
}
