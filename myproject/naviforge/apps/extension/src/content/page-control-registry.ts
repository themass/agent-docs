import { INJECT_SCRIPT_DENIED } from '@naviforge/shared'
import { filterSnapshotLinesByIndex } from '@naviforge/observe'

import { collectFrameSupplement, waitForStableDom } from '../lib/dom-frame-supplement'
import { extractDomFromDocument, extractDomFromEntries } from '../lib/dom-extract'
import { readVisiblePageContent } from '../lib/read-page'
import { pageDocumentToMarkdown } from '../lib/page-markdown'
import { runIsolatedScript } from '../lib/isolated-script'
import { simulateClickElement } from '../lib/simulate-click'
import { simulateKeyPress } from '../lib/simulate-keyboard'
import { simulateDrag, simulateHover } from '../lib/simulate-pointer'
import { handleVideoSubtitleMessage } from '../lib/video-subtitle-overlay'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'
import { BEHAVIOR_RECORD } from '../modules/behavior-forge/messages'
import {
  startBehaviorCapture,
  stopBehaviorCapture,
} from '../modules/behavior-forge/behavior-capture'
import type {
  PageControlContext,
  PageControlPayload,
  PageControlSendResponse,
} from './page-control-types'

export async function dispatchPageControl(
  ctx: PageControlContext,
  action: string,
  payload: PageControlPayload,
  sendResponse: PageControlSendResponse
): Promise<void> {
  switch (action) {
    case 'ping': {
      sendResponse({ ok: true, success: true })
      return
    }
    case 'show_toolkit_palette': {
      const { showToolkitPalette } = await import('../content/toolkit-palette.js')
      showToolkitPalette()
      sendResponse({ success: true })
      return
    }
    case 'get_selection': {
      sendResponse({ success: true, text: ctx.pageSelectionText() })
      return
    }
    case 'pick_element': {
      ctx.startElementPick()
      sendResponse({ success: true, picking: true })
      return
    }
    case 'crop_region': {
      const hint = typeof payload.hint === 'string' ? payload.hint : undefined
      const cropped = await ctx.startRegionCrop(hint ? { hint } : undefined)
      sendResponse(cropped)
      return
    }
    case 'ocr_hud': {
      ctx.showOcrHud({ phase: payload.phase, text: payload.text, path: payload.path })
      sendResponse({ success: true })
      return
    }
    case 'read_page': {
      const data = readVisiblePageContent(document)
      sendResponse({ success: true, data })
      return
    }
    case 'collect_page_signals': {
      const { collectPageSignalRawAsync } = await import('../lib/collect-page-raw.js')
      const data = await collectPageSignalRawAsync(document, location.href)
      sendResponse({ success: true, data })
      return
    }
    case 'to_markdown': {
      const data = pageDocumentToMarkdown(document)
      sendResponse({ success: true, data })
      return
    }
    case 'get_browser_state': {
      const state = await ctx.getPc().getBrowserState()
      const frames = collectFrameSupplement()
      ctx.revision.current += 1
      const mode = payload.mode
      let { header, content } = state as { header: string; content: string }
      if (mode === 'viewport') {
        const visible = new Set(
          ctx
            .entriesFromSelectorMapLocal()
            .filter(({ element }) => {
              const box = element.getBoundingClientRect()
              return box.bottom > 0 && box.right > 0 && box.top < window.innerHeight && box.left < window.innerWidth
            })
            .map(({ index }) => index)
        )
        content = filterSnapshotLinesByIndex(content, visible)
        header = header.replace(/\(full page\)/i, '(viewport)')
        if (!/\(viewport\)/i.test(header)) {
          header = `${header}\nInteractive (viewport):`
        }
      }
      sendResponse({
        success: true,
        data: {
          ...state,
          revision: ctx.revision.current,
          frames: frames || undefined,
          header,
          content,
          mode,
        },
      })
      return
    }
    case 'extract_dom': {
      await ctx.getPc().getBrowserState()
      const kind = (payload as { kind?: 'all' | 'links' | 'buttons' | 'feeds' }).kind ?? 'all'
      const limit = Math.min(96, Math.max(1, (payload as { limit?: number }).limit ?? 48))
      const entries = ctx.entriesFromSelectorMapLocal()
      const data =
        entries.length > 0
          ? extractDomFromEntries(entries, {
              url: location.href,
              title: document.title,
              limit,
              kind,
            })
          : extractDomFromDocument({ url: location.href, title: document.title, limit, kind })
      sendResponse({ success: true, data })
      return
    }
    case 'click_element': {
      if (payload.framePath) {
        const element = ctx.elementForIndex(payload.index!, payload.framePath)
        if (!(element instanceof HTMLElement)) {
          sendResponse({
            success: false,
            error: `frame ${payload.framePath} index ${payload.index} not found`,
          })
          return
        }
        await simulateClickElement(element)
        sendResponse({ success: true, message: `clicked frame ${payload.framePath}[${payload.index}]` })
        return
      }
      const element = ctx.elementForIndex(payload.index!)
      if (!(element instanceof HTMLElement)) {
        sendResponse({ success: false, error: `index ${payload.index} not found` })
        return
      }
      await simulateClickElement(element)
      sendResponse({ success: true, message: `clicked [${payload.index}]` })
      return
    }
    case 'input_text': {
      const r = await ctx.getPc().inputText(payload.index!, payload.text!)
      sendResponse({ success: r.success, message: r.message })
      return
    }
    case 'get_selector': {
      const element = ctx.elementForIndex(payload.index!)
      sendResponse({ success: true, selector: element ? ctx.selectorFor(element) : undefined })
      return
    }
    case 'click_selector': {
      const element = document.querySelector(payload.selector ?? '')
      if (!(element instanceof HTMLElement)) {
        sendResponse({ success: false, error: `selector not found: ${payload.selector}` })
        return
      }
      await simulateClickElement(element)
      sendResponse({ success: true, message: `clicked ${payload.selector}` })
      return
    }
    case 'input_selector': {
      const element = document.querySelector(payload.selector ?? '')
      if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement)) {
        sendResponse({ success: false, error: `input selector not found: ${payload.selector}` })
        return
      }
      element.focus()
      element.value = payload.text ?? ''
      element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText' }))
      element.dispatchEvent(new Event('change', { bubbles: true }))
      sendResponse({ success: true, message: `typed ${payload.selector}` })
      return
    }
    case 'highlight': {
      const targets = payload.targets ?? []
      ctx.bindSync()
      let marked = 0
      const missed: string[] = []
      for (const target of targets) {
        if (!target.label) continue
        const element =
          target.index != null
            ? ctx.elementForIndex(target.index)
            : target.selector
              ? (document.querySelector(target.selector) ?? undefined)
              : undefined
        if (!element) {
          missed.push(
            target.index != null ? `index ${target.index}` : `selector ${target.selector ?? '?'}`
          )
          continue
        }
        ctx.placeMark(target.label, element, target.color)
        element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
        marked += 1
      }
      ctx.scheduleSync()
      sendResponse({
        success: marked > 0,
        marked,
        missed: missed.length ? missed : undefined,
        error:
          marked > 0
            ? undefined
            : `no targets matched (${missed.join(', ') || 'empty targets'}) — re-snapshot and use visible [index] lines`,
      })
      return
    }
    case 'extract_content': {
      const n = Math.min(48, Math.max(1, Math.floor(Number(payload.n ?? 8))))
      const { report, entries } = await ctx.runExtract(n, payload.showHints !== false)
      sendResponse({
        success: report.items.length > 0,
        candidates: entries.length,
        ...ctx.reportPayload(report),
        error: report.items.length
          ? undefined
          : 'no records detected — scroll the list into view and retry',
      })
      return
    }
    case 'mark_items': {
      const requested = payload.items ?? []
      if (!requested.length) {
        sendResponse({ success: false, error: 'items required' })
        return
      }
      ctx.clearMarks()
      const byIndex = new Map(ctx.selectorEntries().map((entry) => [entry.index, entry.element]))
      const missed: number[] = []
      let marked = 0
      for (const item of requested) {
        const element = byIndex.get(item.index)
        if (!element) {
          missed.push(item.index)
          continue
        }
        ctx.placeMark(
          item.label ?? `TOP${marked + 1}`,
          element,
          ctx.TOP_COLORS[marked % ctx.TOP_COLORS.length],
          item.detail
        )
        if (!marked) {
          element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
        }
        marked += 1
      }
      ctx.scheduleSync()
      sendResponse({
        success: marked > 0,
        marked,
        missed: missed.length ? missed : undefined,
        error: marked
          ? undefined
          : `no targets matched (${missed.join(', ')}) — re-run extract_content first`,
      })
      return
    }
    case 'focus_mark': {
      const label = payload.label
      const mark = label ? ctx.marks.get(label) : undefined
      if (!label || !mark || !mark.anchor.isConnected) {
        sendResponse({ success: false, error: `mark not found: ${label ?? '?'}` })
        return
      }
      mark.anchor.scrollIntoView({
        block: 'center',
        inline: 'nearest',
        behavior: 'smooth',
      })
      mark.overlay.setAttribute('data-naviforge-focused', 'true')
      mark.overlay.animate(
        [
          { opacity: 1, transform: mark.overlay.style.transform },
          { opacity: 0.25, transform: mark.overlay.style.transform },
          { opacity: 1, transform: mark.overlay.style.transform },
        ],
        { duration: 700, iterations: 2 }
      )
      window.setTimeout(
        () => mark.overlay.removeAttribute('data-naviforge-focused'),
        1800
      )
      ctx.scheduleSync()
      sendResponse({ success: true, focused: label })
      return
    }
    case 'mark_topn': {
      const n = Math.min(12, Math.max(1, Math.floor(Number(payload.n ?? 4))))
      ctx.clearMarks()
      const { report, entries, byIndex } = await ctx.runExtract(n, payload.showHints !== false)
      const missed: string[] = []
      let marked = 0
      for (const item of report.items) {
        const label = `TOP${item.rank}`
        const element = byIndex.get(item.index)
        if (!element) {
          missed.push(label)
          continue
        }
        ctx.placeMark(
          label,
          element,
          ctx.TOP_COLORS[(item.rank - 1) % ctx.TOP_COLORS.length],
          [item.title, ...Object.values(item.fields)].filter(Boolean).join(' · ')
        )
        if (!marked) {
          element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' })
        }
        marked += 1
      }
      ctx.scheduleSync()
      const offscreen: string[] = []
      for (const item of report.items) {
        const label = `TOP${item.rank}`
        const mark = ctx.marks.get(label)
        if (!mark) continue
        if (!ctx.markInViewport(mark)) offscreen.push(label)
      }
      if (marked) ctx.watchMarksStale()
      sendResponse({
        success: marked > 0,
        marked,
        candidates: entries.length,
        missed: missed.length ? missed : undefined,
        offscreen: offscreen.length ? offscreen : undefined,
        ...ctx.reportPayload(report),
        error: marked
          ? undefined
          : 'no feed items detected — scroll the list into view and retry',
      })
      return
    }
    case 'clear_highlights': {
      ctx.clearMarks()
      await ctx.getPc().cleanUpHighlights().catch(() => {})
      sendResponse({ success: true, cleared: true })
      return
    }
    case 'inject': {
      const kind = payload.injectKind ?? (payload as { kind?: 'css' | 'html' | 'script' }).kind
      const code = payload.code ?? ''
      if (!kind || !code) {
        sendResponse({ success: false, error: 'kind and code required' })
        return
      }
      if (kind === 'css') {
        const style = document.createElement('style')
        style.setAttribute('data-naviforge-inject', 'css')
        style.textContent = code.slice(0, 100_000)
        document.documentElement.appendChild(style)
        sendResponse({ success: true, message: 'css injected' })
        return
      }
      if (kind === 'html') {
        const host = document.createElement('div')
        host.setAttribute('data-naviforge-inject', 'html')
        host.style.cssText = 'position:relative;z-index:2147483645;'
        host.innerHTML = code.slice(0, 100_000)
        document.documentElement.appendChild(host)
        sendResponse({ success: true, message: 'html injected' })
        return
      }
      if (kind === 'script') {
        if (!payload.allowScript) {
          sendResponse({
            success: false,
            error: INJECT_SCRIPT_DENIED,
          })
          return
        }
        const ran = await runIsolatedScript(code)
        if (!ran.ok) {
          sendResponse({ success: false, error: ran.error })
          return
        }
        sendResponse({
          success: true,
          message: `script ok ${JSON.stringify(ran.result).slice(0, 200)}`,
        })
        return
      }
      sendResponse({ success: false, error: `unknown inject kind ${kind}` })
      return
    }
    case 'execute_js': {
      const timeoutMs = Math.min(
        30_000,
        Math.max(1000, typeof payload.timeout_ms === 'number' ? payload.timeout_ms : 15_000)
      )
      const ran = await runIsolatedScript(payload.code ?? '', timeoutMs)
      if (!ran.ok) {
        sendResponse({ success: false, error: ran.error })
        return
      }
      sendResponse({ success: true, result: ran.result })
      return
    }
    case 'navigate': {
      const nav = payload.action
      if (nav === 'back') {
        history.back()
        sendResponse({ success: true, message: 'navigated back' })
        return
      }
      if (nav === 'forward') {
        history.forward()
        sendResponse({ success: true, message: 'navigated forward' })
        return
      }
      if (nav === 'reload') {
        location.reload()
        sendResponse({ success: true, message: 'reloaded' })
        return
      }
      if (nav === 'url' && payload.url) {
        location.assign(payload.url)
        sendResponse({ success: true, message: `opened ${payload.url}` })
        return
      }
      sendResponse({ success: false, error: 'action(back|forward|reload|url) required' })
      return
    }
    case 'hide_capture_chrome': {
      await ctx.hideCaptureChrome()
      sendResponse({ success: true })
      return
    }
    case 'restore_capture_chrome': {
      await ctx.restoreCaptureChrome()
      sendResponse({ success: true })
      return
    }
    case 'scroll': {
      const scrolled = await ctx.performAgentScroll(payload)
      sendResponse({
        success: true,
        message: 'scrolled',
        ...scrolled,
      })
      return
    }
    case 'screenshot_metrics': {
      sendResponse({
        success: true,
        scrollY: window.scrollY,
        innerHeight: window.innerHeight,
        innerWidth: window.innerWidth,
        scrollHeight: document.documentElement.scrollHeight,
        devicePixelRatio: window.devicePixelRatio || 1,
      })
      return
    }
    case 'scroll_to_y': {
      const y = Number(payload.y ?? 0)
      const behavior =
        (payload as { behavior?: ScrollBehavior }).behavior === 'instant'
          ? 'instant'
          : 'smooth'
      window.scrollTo({ top: Math.max(0, y), behavior })
      await waitForStableDom(1200, 120)
      sendResponse({ success: true, scrollY: window.scrollY })
      return
    }
    case 'wait': {
      const deadline = Date.now() + (payload.timeout_ms ?? 10_000)
      const waitKind = payload.waitKind ?? (payload as { kind?: string }).kind
      if (waitKind === 'text' && payload.text) {
        while (Date.now() < deadline) {
          if (document.body?.innerText.includes(payload.text)) {
            sendResponse({ success: true, message: `text found: ${payload.text}` })
            return
          }
          await new Promise((resolve) => setTimeout(resolve, 200))
        }
        sendResponse({ success: false, error: `text not found: ${payload.text}` })
        return
      }
      const quietMs = waitKind === 'network_idle' ? 800 : 500
      const stable = await waitForStableDom(Math.max(500, deadline - Date.now()), quietMs)
      if (stable.ok) {
        sendResponse({
          success: true,
          message: waitKind === 'network_idle' ? 'network_idle (dom quiet)' : 'page stable',
        })
        return
      }
      sendResponse({ success: false, error: 'wait stable timeout' })
      return
    }
    case 'press': {
      const key = payload.key
      if (!key) {
        sendResponse({ success: false, error: 'key required' })
        return
      }
      const target = (document.activeElement as HTMLElement | null) ?? document.body
      simulateKeyPress(target, key, payload.modifiers ?? [])
      sendResponse({
        success: true,
        message: `pressed ${(payload.modifiers ?? []).join('+')}${payload.modifiers?.length ? '+' : ''}${key}`,
      })
      return
    }
    case 'select_option': {
      const element = ctx.elementForIndex(payload.index!)
      if (!(element instanceof HTMLSelectElement)) {
        sendResponse({ success: false, error: `index ${payload.index} is not a select` })
        return
      }
      const value = payload.value ?? payload.text ?? ''
      const option = [...element.options].find(
        (opt) => opt.value === value || opt.textContent?.trim() === value.trim()
      )
      if (!option) {
        sendResponse({ success: false, error: `option not found: ${value}` })
        return
      }
      await simulateClickElement(element)
      element.value = option.value
      element.dispatchEvent(new Event('change', { bubbles: true }))
      sendResponse({ success: true, message: `selected ${option.textContent?.trim() ?? option.value}` })
      return
    }
    case 'set_checked': {
      const element = ctx.elementForIndex(payload.index!)
      if (!(element instanceof HTMLInputElement)) {
        sendResponse({ success: false, error: `index ${payload.index} is not an input` })
        return
      }
      if (element.type !== 'checkbox' && element.type !== 'radio') {
        sendResponse({ success: false, error: 'input is not checkbox/radio' })
        return
      }
      const checked = payload.checked === true
      await simulateClickElement(element)
      element.checked = checked
      element.dispatchEvent(new Event('input', { bubbles: true }))
      element.dispatchEvent(new Event('change', { bubbles: true }))
      sendResponse({ success: true, message: `checked=${checked}` })
      return
    }
    case 'upload_file': {
      const element = ctx.elementForIndex(payload.index!)
      if (!(element instanceof HTMLInputElement) || element.type !== 'file') {
        sendResponse({ success: false, error: `index ${payload.index} is not file input` })
        return
      }
      const raw = payload.contentBase64 ?? ''
      if (!raw || !payload.filename) {
        sendResponse({ success: false, error: 'filename and contentBase64 required' })
        return
      }
      const binary = atob(raw)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
      const file = new File([bytes], payload.filename)
      const transfer = new DataTransfer()
      transfer.items.add(file)
      element.files = transfer.files
      element.dispatchEvent(new Event('input', { bubbles: true }))
      element.dispatchEvent(new Event('change', { bubbles: true }))
      sendResponse({ success: true, message: `uploaded ${payload.filename}` })
      return
    }
    case 'hover': {
      const element = ctx.elementForIndex(payload.index!)
      if (!(element instanceof HTMLElement)) {
        sendResponse({ success: false, error: `index ${payload.index} not found` })
        return
      }
      element.scrollIntoView({ block: 'center', inline: 'center', behavior: 'auto' })
      simulateHover(element)
      sendResponse({ success: true, message: `hover [${payload.index}]` })
      return
    }
    case 'drag': {
      const from = ctx.elementForIndex(payload.fromIndex!)
      const to = ctx.elementForIndex(payload.toIndex!)
      if (!(from instanceof HTMLElement) || !(to instanceof HTMLElement)) {
        sendResponse({ success: false, error: 'fromIndex/toIndex not found' })
        return
      }
      await simulateDrag(from, to)
      sendResponse({
        success: true,
        message: `dragged [${payload.fromIndex}] → [${payload.toIndex}]`,
      })
      return
    }
    case 'clean_up_highlights': {
      ctx.clearMarks()
      await ctx.getPc().cleanUpHighlights()
      sendResponse({ success: true })
      return
    }
    case 'video_subtitles': {
      sendResponse(
        handleVideoSubtitleMessage(
          payload as {
            op?: string
            cues?: Array<{ start: number; end: number; text: string; translated: string }>
          }
        )
      )
      return
    }
    case 'behavior_recording_hud_show': {
      const copy = payload.copy as import('../modules/behavior-forge/recording-hud-copy.js').RecordingHudCopy
      const initial = (payload.state ?? {}) as import('../modules/behavior-forge/recording-hud.js').RecordingHudState
      const pos = payload.pos as { x: number; y: number } | null | undefined
      const {
        hideBehaviorRecordingHud,
        isBehaviorRecordingHudVisible,
        showBehaviorRecordingHud,
        updateBehaviorRecordingHud,
      } = await import('../modules/behavior-forge/recording-hud.js')

      let liveState: import('../modules/behavior-forge/recording-hud.js').RecordingHudState = {
        phase: initial.phase ?? (initial.recording ? 'recording' : 'idle'),
        recording: Boolean(initial.recording),
        eventCount: initial.eventCount ?? 0,
        savedCount: initial.savedCount ?? null,
        error: initial.error,
        pageUrl: initial.pageUrl ?? (initial.recording ? location.href : undefined),
        pageTitle: initial.pageTitle ?? (initial.recording ? document.title : undefined),
      }

      const syncHudGlobal = (
        patch: Partial<import('../modules/behavior-forge/recording-hud.js').RecordingHudState>
      ): void => {
        void safeRuntimeSendMessage({
          type: 'BEHAVIOR_RECORDING_HUD',
          action: 'phase_update',
          phase: patch.phase ?? liveState.phase,
          savedCount: patch.savedCount !== undefined ? patch.savedCount : liveState.savedCount,
          error: patch.error !== undefined ? patch.error : liveState.error ?? null,
        })
      }

      if (isBehaviorRecordingHudVisible()) {
        liveState = {
          ...liveState,
          ...initial,
          phase: initial.phase ?? liveState.phase,
          recording: initial.recording ?? liveState.recording,
          eventCount: initial.eventCount ?? liveState.eventCount,
        }
      }

      let lastRemoteStatusPoll = 0

      const paint = (): void => {
        if (isBehaviorRecordingHudVisible()) updateBehaviorRecordingHud(copy, liveState)
      }

      const refreshStatus = async (): Promise<void> => {
        const res = (await safeRuntimeSendMessage({
          type: BEHAVIOR_RECORD,
          action: 'status',
        })) as { recording?: boolean; eventCount?: number; originUrl?: string; pageTitle?: string } | undefined
        if (!res) return
        if (
          liveState.phase === 'saving' ||
          liveState.phase === 'saved' ||
          liveState.phase === 'error'
        ) {
          return
        }
        liveState = {
          ...liveState,
          phase: res.recording ? 'recording' : 'idle',
          recording: Boolean(res.recording),
          eventCount: res.eventCount ?? 0,
          pageUrl: res.originUrl ?? liveState.pageUrl,
          pageTitle: res.pageTitle ?? liveState.pageTitle,
        }
        paint()
      }

      const hooks = {
        onStart: () => {
          liveState = {
            ...liveState,
            phase: 'recording',
            recording: true,
            savedCount: null,
            error: undefined,
          }
          syncHudGlobal({ phase: 'recording', savedCount: null, error: undefined })
          paint()
          void safeRuntimeSendMessage({ type: BEHAVIOR_RECORD, action: 'start' }).then(() => refreshStatus())
        },
        onStop: () => {
          liveState = {
            ...liveState,
            phase: 'saving',
            recording: true,
          }
          void (async () => {
            await safeRuntimeSendMessage({
              type: 'BEHAVIOR_RECORDING_HUD',
              action: 'phase_update',
              phase: 'saving',
            })
            paint()
            const res = await safeRuntimeSendMessage({ type: BEHAVIOR_RECORD, action: 'stop' })
            const ok = (res as { ok?: boolean })?.ok !== false
            const record = (res as { record?: { eventCount?: number } })?.record
            const count = record?.eventCount ?? liveState.eventCount
            if (!ok) {
              const error = (res as { error?: string })?.error ?? copy.error
              liveState = {
                phase: 'error',
                recording: false,
                eventCount: 0,
                error,
              }
              await safeRuntimeSendMessage({
                type: 'BEHAVIOR_RECORDING_HUD',
                action: 'phase_update',
                phase: 'error',
                savedCount: null,
                error,
              })
            } else {
              liveState = {
                phase: 'saved',
                recording: false,
                eventCount: 0,
                savedCount: count,
              }
              await safeRuntimeSendMessage({
                type: 'BEHAVIOR_RECORDING_HUD',
                action: 'phase_update',
                phase: 'saved',
                savedCount: count,
                error: null,
              })
            }
            paint()
          })()
        },
        onViewReplay: () => {
          void safeRuntimeSendMessage({ type: 'BEHAVIOR_RECORDING_HUD', action: 'open_replay' })
        },
        onRecordAgain: () => {
          liveState = { phase: 'idle', recording: false, eventCount: 0, savedCount: null, error: undefined }
          void safeRuntimeSendMessage({
            type: 'BEHAVIOR_RECORDING_HUD',
            action: 'phase_update',
            phase: 'idle',
            savedCount: null,
            error: null,
          })
          paint()
        },
        onClose: () => {
          void safeRuntimeSendMessage({ type: 'BEHAVIOR_RECORDING_HUD', action: 'close' })
          hideBehaviorRecordingHud()
        },
        onPoll: () => {
          if (liveState.recording && liveState.phase === 'recording') {
            liveState = {
              ...liveState,
              pageUrl: location.href,
              pageTitle: document.title,
            }
            paint()
            const now = Date.now()
            if (now - lastRemoteStatusPoll > 3000) {
              lastRemoteStatusPoll = now
              void refreshStatus()
            }
          }
        },
        onPosition: (x, y) => {
          void safeRuntimeSendMessage({ type: 'BEHAVIOR_RECORDING_HUD', action: 'save_pos', x, y })
        },
      }

      showBehaviorRecordingHud(copy, liveState, hooks, { pos: pos ?? null })
      sendResponse({ success: true, visible: true })
      return
    }
    case 'behavior_recording_hud_hide': {
      const { hideBehaviorRecordingHud } = await import('../modules/behavior-forge/recording-hud.js')
      hideBehaviorRecordingHud()
      sendResponse({ success: true })
      return
    }
    case 'behavior_capture_start': {
      const sessionId = typeof payload.sessionId === 'string' ? payload.sessionId : ''
      const captureDom = payload.captureDom !== false
      const timeOffsetMs = typeof payload.timeOffsetMs === 'number' ? payload.timeOffsetMs : 0
      if (!sessionId) {
        sendResponse({ success: false, error: 'sessionId required' })
        return
      }
      stopBehaviorCapture()
      const { startRrwebCapture, stopRrwebCapture } = await import(
        '../modules/behavior-forge/rrweb-capture.js'
      )
      const { startRecordingLiveOverlay, stopRecordingLiveOverlay } = await import(
        '../modules/behavior-forge/recording-live-overlay.js'
      )
      stopRrwebCapture()
      stopRecordingLiveOverlay()
      startRecordingLiveOverlay()
      startBehaviorCapture(sessionId, (events) => {
        void safeRuntimeSendMessage({
          type: BEHAVIOR_RECORD,
          action: 'batch',
          sessionId,
          events,
        })
      }, { timeOffsetMs })
      if (captureDom) {
        startRrwebCapture(sessionId, (events) => {
          void safeRuntimeSendMessage({
            type: BEHAVIOR_RECORD,
            action: 'rrweb_batch',
            sessionId,
            events,
          })
        })
      }
      sendResponse({ success: true })
      return
    }
    case 'behavior_capture_stop': {
      stopBehaviorCapture()
      const { stopRrwebCapture } = await import('../modules/behavior-forge/rrweb-capture.js')
      const { stopRecordingLiveOverlay } = await import(
        '../modules/behavior-forge/recording-live-overlay.js'
      )
      stopRrwebCapture()
      stopRecordingLiveOverlay()
      sendResponse({ success: true })
      return
    }
    case 'genius_fall_hud_toggle':
    case 'genius_fall_hud_ensure':
    case 'genius_fall_hud_update':
    case 'genius_fall_hud_hide': {
      const {
        hideGeniusFallHud,
        showGeniusFallHud,
        toggleGeniusFallHud,
        updateGeniusFallHud,
        isGeniusFallHudVisible,
      } = await import('../modules/genius-fall/genius-fall-hud.js')
      const hooks = {
        onMove: (x: number, y: number) => {
          void safeRuntimeSendMessage({ type: 'GENIUS_FALL_HUD', action: 'move', x, y })
        },
        onPrefsChange: (patch: Record<string, unknown>) => {
          void safeRuntimeSendMessage({ type: 'GENIUS_FALL_HUD', action: 'prefs', prefs: patch })
        },
        onRefresh: () => {
          void safeRuntimeSendMessage({ type: 'GENIUS_FALL_HUD', action: 'refresh' })
        },
        onOpenPanel: () => {
          void safeRuntimeSendMessage({ type: 'GENIUS_FALL_HUD', action: 'open_panel' })
        },
        onClose: () => {
          hideGeniusFallHud()
          void safeRuntimeSendMessage({ type: 'GENIUS_FALL_HUD', action: 'close' })
        },
      }
      if (action === 'genius_fall_hud_hide') {
        hideGeniusFallHud()
        sendResponse({ success: true, visible: false })
        return
      }
      const state = payload.state as import('../modules/genius-fall/hud-types.js').GeniusFallHudState
      const prefs = payload.prefs as import('../modules/genius-fall/hud-types.js').GeniusFallHudPrefs
      if (action === 'genius_fall_hud_update') {
        if (isGeniusFallHudVisible()) updateGeniusFallHud(state, prefs)
        sendResponse({ success: true, visible: isGeniusFallHudVisible() })
        return
      }
      if (action === 'genius_fall_hud_ensure') {
        if (!isGeniusFallHudVisible()) {
          showGeniusFallHud(state, prefs, hooks)
        } else {
          updateGeniusFallHud(state, prefs)
        }
        sendResponse({ success: true, visible: true })
        return
      }
      const visible = toggleGeniusFallHud(state, prefs, hooks)
      sendResponse({ success: true, visible })
      return
    }
    default:
      sendResponse({ success: false, error: `unknown action ${action}` })
  }
}
