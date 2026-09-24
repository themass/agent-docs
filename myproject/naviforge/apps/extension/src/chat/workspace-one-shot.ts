import type { MutableRefObject } from 'react'
import { RUN_STATUS, type WorkspaceRunStatus } from '../lib/run-phase'
import type { WorkspaceEntry } from '@naviforge/runtime'
import {
  askAboutPage,
  pickedElementExcerpt,
  resolveOneShotQuestion,
} from '@naviforge/runtime'
import {
  getActiveModelProfile,
  loadModelProfiles,
  profileToLlmConfig,
  type LlmConfig,
} from '../lib/llm-profiles'
import { loadNewApiAuth } from '../lib/newapi-auth'
import { syncManagedProfilesFromNewApi } from '../lib/newapi-sync'

import { createChromeDomPlane } from '../lib/chrome-dom-plane'
import {
  IMAGE_ASK_DEFAULT_QUESTION,
  IMAGE_FILE_RE,
  shotAskFromText,
} from '../lib/image-ask'
import { workspaceRpc } from '../lib/local-workspace'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'
import type { PickedElement } from './workspace-helpers'
import { pickedLabel } from './workspace-helpers'

export type OneShotActionsDeps = {
  llm: LlmConfig
  task: string
  pageAskBusy: boolean
  pickedElement: PickedElement | null
  imageAttachment: { dataUrl: string; label: string } | null
  runningRef: MutableRefObject<boolean>
  pageAskAbortRef: MutableRefObject<AbortController | null>
  explainAfterPickRef: MutableRefObject<boolean>
  setPageAskBusy(value: boolean): void
  setStatus(value: WorkspaceRunStatus): void
  setStatusDetail(value: string | null): void
  setTask(value: string | ((current: string) => string)): void
  setRunOutcome(value: {
    kind: 'success' | 'failed' | 'blocked' | 'waiting' | 'cancelled'
    title: string
    message: string
  } | null): void
  setTokenUsage(value: {
    lastPrompt: number
    lastCompletion: number
    runTotal: number
  } | null): void
  setImageAttachment(value: { dataUrl: string; label: string } | null): void
  appendLocal(
    type: 'user.task' | 'run.result' | 'run.error',
    payload: Record<string, unknown>
  ): void
  push(line: string): void
  bindActiveTab(): Promise<chrome.tabs.Tab | null>
  pickElement(): Promise<void>
}

export function createOneShotActions(deps: OneShotActionsDeps) {
  async function resolveOneShotLlm(): Promise<LlmConfig> {
    const auth = await loadNewApiAuth()
    if (auth.mode === 'managed') {
      const profilesBefore = await loadModelProfiles()
      const activeBefore = getActiveModelProfile(profilesBefore)
      const staleHttps = /^https:\/\/gpt\.sspacee\.com/i.test(activeBefore.baseURL)
      await syncManagedProfilesFromNewApi({ force: staleHttps })
      const profiles = await loadModelProfiles()
      return profileToLlmConfig(getActiveModelProfile(profiles))
    }
    return deps.llm
  }

  async function runOneShotAsk(opts: {
    title: string
    question: string
    screenshot: boolean
    imageDataUrl?: string
    textExcerpt?: string
  }): Promise<void> {
    const question = opts.question.trim()
    if (!question || deps.pageAskBusy || deps.runningRef.current) return
    deps.setPageAskBusy(true)
    deps.setStatus(RUN_STATUS.PLANNING)
    deps.setStatusDetail(opts.imageDataUrl ? '正在看图…' : '正在看当前页…')
    deps.setTask('')
    deps.setRunOutcome(null)
    const tab = await deps.bindActiveTab()
    if (!opts.imageDataUrl && !tab?.id) {
      deps.setPageAskBusy(false)
      deps.setStatus(RUN_STATUS.FAILED)
      deps.setStatusDetail(null)
      deps.setRunOutcome({ kind: 'failed', title: `无法${opts.title}`, message: '请先绑定一个普通网页标签' })
      deps.setTask((current) => (current.trim() ? current : question))
      return
    }
    deps.appendLocal('user.task', {
      text: `${opts.title}: ${question}`,
      imageDataUrl: opts.imageDataUrl,
      imageLabel: opts.textExcerpt,
    })
    const llm = await resolveOneShotLlm()
    if (!llm.apiKey) {
      deps.setPageAskBusy(false)
      deps.setStatus(RUN_STATUS.FAILED)
      deps.setStatusDetail(null)
      deps.setRunOutcome({ kind: 'failed', title: '未配置模型', message: '请先在设置中填写 API Key' })
      deps.setTask((current) => (current.trim() ? current : question))
      return
    }
    const abort = new AbortController()
    deps.pageAskAbortRef.current = abort
    try {
      let imageDataUrl = opts.imageDataUrl
      let excerpt = opts.textExcerpt
      if (!imageDataUrl) {
        if (!tab?.id) throw new Error('请先绑定一个普通网页标签')
        const dom = createChromeDomPlane(() => tab.id!)
        if (opts.screenshot) {
          const capture = dom.screenshot
          if (!capture) throw new Error('当前环境不支持截图')
          const [shot, snap] = excerpt
            ? [await capture.call(dom), null]
            : await Promise.all([capture.call(dom), dom.snapshot()])
          if (!shot.ok || !shot.data?.dataUrl) {
            throw new Error(shot.ok ? '截图失败' : shot.error.message)
          }
          imageDataUrl = shot.data.dataUrl
          if (!excerpt && snap?.ok) excerpt = snap.data.content
        } else if (!excerpt) {
          if (!dom.readPage) throw new Error('当前环境不支持读正文')
          const read = await dom.readPage()
          if (!read.ok) throw new Error(read.error.message)
          excerpt = read.data.text
        }
        if (!opts.screenshot && !excerpt?.trim()) throw new Error('当前页没有可读正文')
      }
      const { answer, usage } = await askAboutPage({
        llm,
        question,
        imageDataUrl,
        url: tab?.url,
        title: tab?.title,
        textExcerpt: excerpt,
        signal: abort.signal,
      })
      if (usage) {
        deps.setTokenUsage({
          lastPrompt: usage.promptTokens,
          lastCompletion: usage.completionTokens,
          runTotal: usage.totalTokens,
        })
      }
      deps.appendLocal('run.result', { text: answer })
      deps.setStatus(RUN_STATUS.COMPLETED)
      deps.setRunOutcome({ kind: 'success', title: `${opts.title}完成`, message: answer.slice(0, 200) })
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        deps.setStatus(RUN_STATUS.CANCELLED)
        deps.setRunOutcome({ kind: 'cancelled', title: '已停止', message: `${opts.title}已取消` })
      } else {
        const message = (error as Error).message
        deps.appendLocal('run.error', { message })
        deps.setStatus(RUN_STATUS.FAILED)
        deps.setRunOutcome({ kind: 'failed', title: `${opts.title}失败`, message })
      }
    } finally {
      deps.pageAskAbortRef.current = null
      deps.setPageAskBusy(false)
      deps.setStatusDetail(null)
    }
  }

  async function latestShotPath(): Promise<string | null> {
    const { entries } = await workspaceRpc<{ entries: WorkspaceEntry[] }>('list', { dir: 'shots' })
    const last = entries.filter((entry) => entry.kind === 'file' && IMAGE_FILE_RE.test(entry.name)).at(-1)
    return last ? `shots/${last.name}` : null
  }

  async function askAboutImage(questionText?: string): Promise<void> {
    const typed = (questionText ?? deps.task).trim()
    const attached = deps.imageAttachment
    if (attached) {
      const question = typed || IMAGE_ASK_DEFAULT_QUESTION
      deps.setImageAttachment(null)
      await runOneShotAsk({
        title: '看图',
        question,
        screenshot: false,
        imageDataUrl: attached.dataUrl,
        textExcerpt: `图片来源：${attached.label}`,
      })
      return
    }
    const ref = shotAskFromText(typed)
    if (ref) {
      const question = typed || IMAGE_ASK_DEFAULT_QUESTION
      try {
        const path = ref.kind === 'path' ? ref.path : await latestShotPath()
        if (!path) {
          deps.setRunOutcome({ kind: 'failed', title: '看图失败', message: '工作区 shots/ 里还没有截图' })
          return
        }
        const { dataUrl } = await workspaceRpc<{ dataUrl: string }>('readDataUrl', { path })
        await runOneShotAsk({
          title: '看图',
          question,
          screenshot: false,
          imageDataUrl: dataUrl,
          textExcerpt: `图片来源：${path}`,
        })
      } catch (error) {
        deps.setRunOutcome({ kind: 'failed', title: '看图失败', message: (error as Error).message })
      }
      return
    }
    await askAboutCurrentPage(questionText)
  }

  async function askAboutCurrentPage(questionText?: string): Promise<void> {
    const question = resolveOneShotQuestion('page', questionText ?? deps.task)
    await runOneShotAsk({ title: '页面问答', question, screenshot: true })
  }

  async function summarizeCurrentPage(): Promise<void> {
    const question = resolveOneShotQuestion('summarize', deps.task)
    await runOneShotAsk({ title: '总结本页', question, screenshot: false })
  }

  async function explainPickedElement(target?: PickedElement): Promise<void> {
    const element = target ?? deps.pickedElement
    if (element) {
      await runOneShotAsk({
        title: '解释选中',
        question: resolveOneShotQuestion('explain', deps.task, pickedLabel(element)),
        screenshot: true,
        textExcerpt: pickedElementExcerpt(element),
      })
      return
    }
    if (deps.pageAskBusy || deps.runningRef.current) return
    const tab = await deps.bindActiveTab()
    if (!tab?.id) {
      deps.setRunOutcome({ kind: 'failed', title: '无法解释选中', message: '请先打开一个普通网页' })
      return
    }
    try {
      const selected = (await safeRuntimeSendMessage({
        type: 'PAGE_CONTROL',
        action: 'get_selection',
        targetTabId: tab.id,
      })) as { text?: string } | undefined
      const text = selected?.text?.trim() ?? ''
      if (text) {
        await runOneShotAsk({
          title: '解释选中',
          question: resolveOneShotQuestion('explain', deps.task, text.slice(0, 40)),
          screenshot: true,
          textExcerpt: text,
        })
        return
      }
    } catch {
      /* content script missing — fall through to click-to-pick */
    }
    deps.explainAfterPickRef.current = true
    await deps.pickElement()
  }

  async function copyPageArticle(): Promise<void> {
    if (deps.pageAskBusy || deps.runningRef.current) return
    const tab = await deps.bindActiveTab()
    if (!tab?.id) {
      deps.setRunOutcome({ kind: 'failed', title: '无法复制', message: '请先绑定一个普通网页标签' })
      return
    }
    const dom = createChromeDomPlane(() => tab.id!)
    if (!dom.readPage) {
      deps.setRunOutcome({ kind: 'failed', title: '无法复制', message: '当前环境不支持读正文' })
      return
    }
    const read = await dom.readPage()
    if (!read.ok) {
      deps.setRunOutcome({ kind: 'failed', title: '无法复制', message: read.error.message })
      return
    }
    const text = read.data.text.trim()
    if (!text) {
      deps.setRunOutcome({ kind: 'failed', title: '无法复制', message: '当前页没有可读正文' })
      return
    }
    await navigator.clipboard.writeText(text)
    deps.appendLocal('run.result', { text: `已复制 ${text.length} 字` })
    deps.setRunOutcome({ kind: 'success', title: '已复制正文', message: `${text.length} 字` })
    deps.push(`✓ 已复制正文 ${text.length} 字`)
  }

  return {
    runOneShotAsk,
    latestShotPath,
    askAboutImage,
    askAboutCurrentPage,
    summarizeCurrentPage,
    explainPickedElement,
    copyPageArticle,
  }
}
