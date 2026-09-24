import { PageController } from '@page-agent/page-controller'

import { documentForFramePath, waitForStableDom } from '../lib/dom-frame-supplement'
import {
  BUNDLED_PROFILES,
  collectCandidates,
  extractContent,
  gatherInteractiveElements,
  narrowEntries,
  profileFor,
  proposeProfile,
  type ContentItem,
  type ExtractReport,
  type SiteProfile,
} from '../lib/content-extract'
import { listProfiles, rememberProfile } from '../lib/site-profile-store'
import { titleForElement } from '../lib/feed-mark'
import { STORAGE } from '../lib/settings'
import { isPresenceLive, parseAgentPresence } from '../lib/agent-presence'
import { pageAtBottom, pickLargestScrollable } from '../lib/scroll-page'
import {
  entriesFromSelectorMap,
  elementFromSelectorMap,
  selectorEntriesFromMap,
} from '../lib/selector-resolver'
import { installPageControlListener } from '../content/page-control-listener'
import { dispatchPageControl } from '../content/page-control-registry'
import type { PageControlContext } from '../content/page-control-types'
import {
  extensionRuntimeAlive,
  installExtensionContextGuard,
  isExtensionContextInvalidated,
  runIfExtensionAlive,
  safeRuntimeSendMessage,
  safeStorageLocalGet,
} from '../lib/extension-runtime'

const INTERACTIVE = 'a,button,input,textarea,select,[role="button"],[role="link"]'

export default defineContentScript({
  matches: ['<all_urls>'],
  runAt: 'document_end',
  main(ctx) {
    let teardownPresence: (() => void) | null = null
    const removeContextGuard = installExtensionContextGuard(() => teardownPresence?.())
    ctx.onInvalidated(() => {
      removeContextGuard()
      teardownPresence?.()
    })

    let pc: PageController | null = null
    const revisionRef = { current: 0 }
    /** Agent run on this tab: lock mask + numbered highlights. TOPN marks stay separate. */
    let agentLive = false
    let lastSelection = ''
    let lastSelectionAt = 0
    document.addEventListener('selectionchange', () => {
      const text = pageSelectionText(true)
      if (!text) return
      lastSelection = text.slice(0, 4_000)
      lastSelectionAt = Date.now()
    })
    function pageSelectionText(liveOnly = false): string {
      const live = (window.getSelection()?.toString() ?? '').replace(/\s+/g, ' ').trim()
      if (live) return live
      const el = document.activeElement
      if (
        (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) &&
        el.selectionEnd != null &&
        el.selectionStart != null &&
        el.selectionEnd > el.selectionStart
      ) {
        return el.value.slice(el.selectionStart, el.selectionEnd).replace(/\s+/g, ' ').trim()
      }
      if (liveOnly) return ''
      return Date.now() - lastSelectionAt < 60_000 ? lastSelection : ''
    }
    const TOP_COLORS = ['#ff5c35', '#fbbf24', '#22c55e', '#3b82f6', '#a855f7', '#ec4899']
    type Mark = {
      element: Element
      anchor: HTMLElement
      overlay: HTMLElement
      badge: HTMLElement
      tooltip?: HTMLElement
      color: string
      label: string
    }
    const marks = new Map<string, Mark>()
    let syncBound = false
    let syncRaf = 0
    let markFollowRaf = 0
    let cancelPick: (() => void) | undefined
    let cancelCrop: (() => void) | undefined

    function refreshPc(live: boolean): PageController {
      agentLive = live
      pc?.dispose()
      pc = new PageController({
        enableMask: live,
        viewportExpansion: -1,
        highlightOpacity: live ? 0.12 : 0,
        highlightLabelOpacity: live ? 0.85 : 0,
      })
      if (live) pc.initMask()
      return pc
    }

    function getPc(): PageController {
      if (!pc) return refreshPc(agentLive)
      return pc
    }

    async function setAgentLive(live: boolean, action?: string): Promise<void> {
      if (live === agentLive && pc) {
        if (live) await pc.showMask()
        else {
          await pc.hideMask()
          await pc.cleanUpHighlights()
        }
        setLockHint(live, action)
        return
      }
      refreshPc(live)
      if (live) await getPc().showMask()
      setLockHint(live, action)
    }

    function setLockHint(on: boolean, action?: string): void {
      const id = 'naviforge-lock-hint'
      const existing = document.getElementById(id)
      if (!on) {
        existing?.remove()
        return
      }
      const el = existing ?? document.createElement('div')
      el.id = id
      el.textContent = action?.trim() ? `NaviForge · ${action.trim().slice(0, 48)}` : 'NaviForge · 页面已锁定'
      Object.assign(el.style, {
        position: 'fixed',
        top: '12px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: '2147483646',
        pointerEvents: 'none',
        padding: '8px 14px',
        borderRadius: '999px',
        background: 'rgba(15,23,42,0.92)',
        color: '#f8fafc',
        font: '12px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
        letterSpacing: '0.2px',
      })
      if (!existing) document.documentElement.appendChild(el)
    }

    function cssValue(value: string): string {
      return value.replace(/["\\]/g, '\\$&')
    }

    function unique(selector: string): boolean {
      try {
        return document.querySelectorAll(selector).length === 1
      } catch {
        return false
      }
    }

    /** Prefer stable author-owned attributes; structural paths are a last resort. */
    function selectorFor(element: Element): string | undefined {
      if (element.id && unique(`#${CSS.escape(element.id)}`)) return `#${CSS.escape(element.id)}`

      for (const attribute of ['data-testid', 'data-test', 'data-agent-hint', 'name', 'aria-label']) {
        const value = element.getAttribute(attribute)
        if (!value) continue
        const selector = `${element.tagName.toLowerCase()}[${attribute}="${cssValue(value)}"]`
        if (unique(selector)) return selector
      }

      const parts: string[] = []
      let current: Element | null = element
      while (current && current !== document.body && parts.length < 4) {
        const tag = current.tagName.toLowerCase()
        const siblings = current.parentElement
          ? [...current.parentElement.children].filter((item) => item.tagName === current!.tagName)
          : []
        const nth = siblings.length > 1 ? `:nth-of-type(${siblings.indexOf(current) + 1})` : ''
        parts.unshift(`${tag}${nth}`)
        const candidate = parts.join(' > ')
        if (unique(candidate)) return candidate
        current = current.parentElement
      }
      return undefined
    }

    function entriesFromSelectorMapLocal(): Array<{ index: number; element: Element }> {
      return entriesFromSelectorMap(getPc())
    }

    function elementForIndex(index: number, framePath?: string): Element | undefined {
      if (framePath) {
        const doc = documentForFramePath(framePath)
        const items = [...doc.querySelectorAll(INTERACTIVE)]
        return items[index - 1]
      }
      return elementFromSelectorMap(getPc(), index)
    }

    /** Expand tiny link nodes to their card-sized parent (bilibili feed items, etc.). */
    function highlightAnchor(element: Element): HTMLElement {
      let anchor = element as HTMLElement
      let rect = anchor.getBoundingClientRect()
      // A card-sized link is already the correct target. Expanding it again
      // selects the grid/list container and produces one giant box around
      // neighboring records.
      if (rect.width >= 120 && rect.height >= 72) return anchor
      let parent = anchor.parentElement
      while (parent && parent !== document.body) {
        const parentRect = parent.getBoundingClientRect()
        if (parentRect.width >= 120 && parentRect.height >= 72 && parentRect.width <= window.innerWidth * 0.75) {
          anchor = parent
          rect = parentRect
        }
        if (rect.width >= 180 && rect.height >= 110) break
        parent = parent.parentElement
      }
      return anchor
    }

    function placeMark(label: string, element: Element, color = '#ff5c35', detail?: string): void {
      const layer = ensureMarkLayer()
      bindSync()
      const anchor = highlightAnchor(element)
      marks.get(label)?.overlay.remove()
      marks.get(label)?.badge.remove()
      marks.get(label)?.tooltip?.remove()
      element.setAttribute('data-naviforge-mark', label)
      const overlay = document.createElement('div')
      overlay.setAttribute('data-naviforge-overlay', label)
      overlay.style.cssText = [
        'position:fixed',
        'left:0',
        'top:0',
        'box-sizing:border-box',
        `border:3px solid ${color}`,
        `background:${color}22`,
        'border-radius:8px',
        `box-shadow:0 0 0 2px rgba(0,0,0,0.35),0 0 16px 4px ${color}88`,
        'pointer-events:none',
        'z-index:2147483645',
      ].join(';')
      const badge = document.createElement('div')
      badge.textContent = label
      badge.style.cssText = [
        'position:fixed',
        'left:0',
        'top:0',
        'padding:3px 8px',
        'background:#17211f',
        `color:${color}`,
        'font:700 12px/1.2 ui-monospace,monospace',
        'border:2px solid currentColor',
        'border-radius:4px',
        'pointer-events:none',
        'z-index:2147483647',
        'white-space:nowrap',
      ].join(';')
      layer.appendChild(overlay)
      layer.appendChild(badge)
      const tooltip = detail ? document.createElement('div') : undefined
      if (tooltip && detail) {
        tooltip.textContent = detail
        tooltip.style.cssText = [
          'position:fixed',
          'left:0',
          'top:0',
          'display:none',
          'max-width:280px',
          'padding:6px 8px',
          'background:#17211f',
          'color:#fff',
          'font:12px/1.35 system-ui,sans-serif',
          'border:1px solid #52605a',
          'border-radius:4px',
          'pointer-events:none',
          'z-index:2147483647',
        ].join(';')
        layer.appendChild(tooltip)
      }
      const mark: Mark = { element, anchor, overlay, badge, tooltip, color, label }
      if (tooltip) {
        anchor.addEventListener('mouseenter', () => {
          tooltip.style.display = 'block'
          applyMarkGeometry(mark)
        })
        anchor.addEventListener('mouseleave', () => {
          tooltip.style.display = 'none'
        })
      }
      marks.set(label, mark)
      applyMarkGeometry(mark)
      startMarkFollow()
    }

    function selectorEntries(): Array<{ index: number; element: Element; title?: string }> {
      return selectorEntriesFromMap(getPc(), () =>
        gatherInteractiveElements().map((element, index) => ({ index: index + 1, element }))
      )
    }

    type Entries = Array<{ index: number; element: Element; title?: string }>

    /**
     * Lazy feeds render only what has been near the viewport, so a page that
     * looks 8 records deep is 40 deep once walked. Scroll back to where the user
     * left off — this is a read, and a read must not move their page.
     */
    async function primeLazyList(): Promise<void> {
      const start = window.scrollY
      const step = Math.max(240, window.innerHeight - 120)
      let previousHeight = -1
      for (let pass = 0; pass < 10; pass += 1) {
        const height = document.documentElement.scrollHeight
        if (window.scrollY + window.innerHeight >= height - 4) break
        if (height === previousHeight && pass > 1) break
        previousHeight = height
        window.scrollBy(0, step)
        await waitForStableDom(700, 150)
      }
      window.scrollTo(0, start)
    }

    async function collectOnce(
      n: number,
      showHints: boolean,
      visibleOnly: boolean,
      profiles: SiteProfile[] | undefined
    ): Promise<{ report: ExtractReport; entries: Entries }> {
      await getPc().getBrowserState()
      const opts = { url: location.href, n, visibleOnly, profiles }
      const profile = profileFor(location.href, profiles ?? BUNDLED_PROFILES)

      const extractFrom = (all: Entries): { report: ExtractReport; entries: Entries } => {
        const narrowed = narrowEntries(all, profile)
        const entries = narrowed.length ? narrowed : all
        const report = extractContent(collectCandidates(entries), opts)
        if (!report.items.length && narrowed.length && narrowed.length < all.length) {
          return {
            report: extractContent(collectCandidates(all), opts),
            entries: all,
          }
        }
        return { report, entries }
      }

      const snap = selectorEntries()
      let all: Entries = snap
      let result = extractFrom(all)

      if (result.report.items.length < n) {
        const dom = gatherInteractiveElements().map((element, index) => ({
          index: index + 1,
          element,
        }))
        if (dom.length) {
          const fallback = extractFrom(dom)
          if (fallback.report.items.length > result.report.items.length) {
            result = fallback
          }
        }
      }

      return result
    }

    /** Read-only: refresh the snapshot, induce records, and learn a profile if confident. */
    async function runExtract(
      n: number,
      showHints: boolean
    ): Promise<{
      report: ExtractReport
      entries: Entries
      byIndex: Map<number, Element>
    }> {
      const profiles = await listProfiles().catch(() => undefined)
      let { report, entries } = await collectOnce(n, showHints, true, profiles)
      // Only pay for scrolling when what is on screen genuinely was not enough.
      if (report.found < n) {
        await primeLazyList()
        ;({ report, entries } = await collectOnce(n, showHints, false, profiles))
      }
      void rememberProfile(proposeProfile(location.href, report)).catch(() => {})
      return {
        report,
        entries,
        byIndex: new Map(entries.map((entry) => [entry.index, entry.element])),
      }
    }

    function itemsPayload(items: ContentItem[]) {
      return items.map((item) => ({
        label: `TOP${item.rank}`,
        index: item.index,
        title: item.title,
        url: item.url,
        author: item.fields.author,
        views: item.fields.views,
        duration: item.fields.duration,
        fields: item.fields,
        confidence: item.confidence,
      }))
    }

    function reportPayload(report: ExtractReport) {
      return {
        strategy: report.strategy,
        profileId: report.profileId,
        shortfall: report.shortfall,
        items: itemsPayload(report.items),
      }
    }

    function ensureMarkLayer(): HTMLElement {
      let layer = document.getElementById('naviforge-mark-layer')
      if (!layer) {
        layer = document.createElement('div')
        layer.id = 'naviforge-mark-layer'
        layer.style.cssText =
          'position:fixed;inset:0;pointer-events:none;z-index:2147483646;overflow:visible;'
        document.documentElement.appendChild(layer)
      }
      return layer
    }

    function markInViewport(mark: Mark): boolean {
      const rect = mark.anchor.getBoundingClientRect()
      return (
        rect.width > 4 &&
        rect.height > 4 &&
        rect.bottom > 0 &&
        rect.right > 0 &&
        rect.top < window.innerHeight &&
        rect.left < window.innerWidth
      )
    }

    function applyMarkGeometry(mark: Mark): void {
      if (!document.contains(mark.anchor)) return
      const visible = markInViewport(mark)
      const display = visible ? 'block' : 'none'
      mark.overlay.style.display = display
      mark.badge.style.display = display
      if (!visible) return
      const rect = mark.anchor.getBoundingClientRect()
      const pad = 4
      mark.overlay.style.transform = `translate(${Math.max(0, rect.left - pad)}px, ${Math.max(0, rect.top - pad)}px)`
      mark.overlay.style.width = `${Math.max(0, rect.width + pad * 2)}px`
      mark.overlay.style.height = `${Math.max(0, rect.height + pad * 2)}px`
      mark.badge.style.transform = `translate(${Math.max(4, rect.left)}px, ${Math.max(4, rect.top - 24)}px)`
      if (mark.tooltip?.style.display === 'block') {
        mark.tooltip.style.transform = `translate(${Math.max(4, rect.left)}px, ${Math.min(
          window.innerHeight - 48,
          rect.bottom + 8
        )}px)`
      }
    }

    function syncMarks(): void {
      for (const [key, mark] of [...marks.entries()]) {
        if (!mark.anchor.isConnected) {
          mark.overlay.remove()
          mark.badge.remove()
          mark.tooltip?.remove()
          mark.element.removeAttribute('data-naviforge-mark')
          marks.delete(key)
          continue
        }
        applyMarkGeometry(mark)
      }
    }

    function scheduleSync(): void {
      if (syncRaf) return
      syncRaf = requestAnimationFrame(() => {
        syncRaf = 0
        syncMarks()
      })
    }

    function bindSync(): void {
      if (syncBound) return
      syncBound = true
      window.addEventListener('scroll', scheduleSync, true)
      window.addEventListener('resize', scheduleSync)
    }

    function stopMarkFollow(): void {
      if (!markFollowRaf) return
      cancelAnimationFrame(markFollowRaf)
      markFollowRaf = 0
    }

  // ponytail: rAF follow while marks exist — catches inner scroll containers that skip window scroll events
    function startMarkFollow(): void {
      if (markFollowRaf) return
      const tick = () => {
        syncMarks()
        markFollowRaf = marks.size > 0 ? requestAnimationFrame(tick) : 0
      }
      markFollowRaf = requestAnimationFrame(tick)
    }

    let markStaleWatcher: (() => void) | null = null

    function watchMarksStale(): void {
      if (markStaleWatcher) return
      const notify = () => {
        void safeRuntimeSendMessage({ type: 'NAVIFORGE_MARK_STALE' })
        window.removeEventListener('scroll', markStaleWatcher!, true)
        markStaleWatcher = null
      }
      markStaleWatcher = notify
      window.addEventListener('scroll', notify, { capture: true, passive: true })
    }

    function clearMarks(): void {
      stopMarkFollow()
      for (const mark of marks.values()) {
        mark.element.removeAttribute('data-naviforge-mark')
        mark.overlay.remove()
        mark.badge.remove()
        mark.tooltip?.remove()
      }
      marks.clear()
      document.getElementById('naviforge-mark-layer')?.remove()
    }

    type CaptureChromeSaved = {
      markLayerDisplay: string
      lockHintDisplay: string
      highlightDisplay: string
      maskWasShown: boolean
    }
    let captureChromeDepth = 0
    let captureChromeSaved: CaptureChromeSaved | null = null

    async function hideCaptureChrome(): Promise<void> {
      if (captureChromeDepth === 0) {
        const markLayer = document.getElementById('naviforge-mark-layer')
        const lockHint = document.getElementById('naviforge-lock-hint')
        const highlight = document.getElementById('playwright-highlight-container')
        captureChromeSaved = {
          markLayerDisplay: markLayer?.style.display ?? '',
          lockHintDisplay: lockHint?.style.display ?? '',
          highlightDisplay: highlight?.style.display ?? '',
          maskWasShown: agentLive,
        }
        if (markLayer) markLayer.style.display = 'none'
        if (lockHint) lockHint.style.display = 'none'
        if (highlight) highlight.style.display = 'none'
        if (agentLive) await getPc().hideMask()
      }
      captureChromeDepth += 1
    }

    async function restoreCaptureChrome(): Promise<void> {
      if (captureChromeDepth <= 0) return
      captureChromeDepth -= 1
      if (captureChromeDepth > 0 || !captureChromeSaved) return
      const saved = captureChromeSaved
      captureChromeSaved = null
      const markLayer = document.getElementById('naviforge-mark-layer')
      const lockHint = document.getElementById('naviforge-lock-hint')
      const highlight = document.getElementById('playwright-highlight-container')
      if (markLayer) markLayer.style.display = saved.markLayerDisplay
      if (lockHint) lockHint.style.display = saved.lockHintDisplay
      if (highlight) highlight.style.display = saved.highlightDisplay
      if (saved.maskWasShown) await getPc().showMask()
    }

    function largestScrollableElement(): HTMLElement | null {
      const nodes = [...document.querySelectorAll('body *')].filter(
        (node): node is HTMLElement => node instanceof HTMLElement
      )
      const metrics = nodes.map((el) => {
        const style = getComputedStyle(el)
        return {
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight,
          clientWidth: el.clientWidth,
          overflowY: style.overflowY,
        }
      })
      const index = pickLargestScrollable(metrics)
      return index >= 0 ? nodes[index]! : null
    }

    async function performAgentScroll(payload: Record<string, unknown>): Promise<{
      scrollY: number
      atBottom: boolean
      target: 'window' | 'inner' | 'none'
      delta: number
    }> {
      const direction = (payload as { direction?: string }).direction
      const amount = (payload as { amount?: number }).amount
      const beforeY = window.scrollY
      const doc = document.documentElement

      const scrollWindowBy = (delta: number) => {
        window.scrollBy({ top: delta, behavior: 'auto' })
      }

      if (payload.to === 'top') {
        window.scrollTo({ top: 0, behavior: 'auto' })
      } else if (payload.to === 'bottom') {
        window.scrollTo({ top: doc.scrollHeight, behavior: 'auto' })
      } else if (payload.to === 'y' && typeof payload.y === 'number') {
        window.scrollTo({ top: Math.max(0, payload.y), behavior: 'auto' })
      } else if (typeof payload.y === 'number') {
        scrollWindowBy(payload.y)
      } else if (direction === 'down' || direction === 'up') {
        const delta =
          typeof amount === 'number' && Number.isFinite(amount)
            ? amount
            : Math.round(window.innerHeight * 0.85)
        scrollWindowBy(direction === 'down' ? delta : -delta)
      } else {
        scrollWindowBy(Math.round(window.innerHeight * 0.85))
      }

      await waitForStableDom(1200, 120)

      let target: 'window' | 'inner' | 'none' = 'window'
      let delta = window.scrollY - beforeY
      let atBottom = pageAtBottom(window.scrollY, window.innerHeight, doc.scrollHeight)

      // ponytail: window scroll no-op on overflow containers — try largest inner scroller
      if (Math.abs(delta) < 2 && payload.to !== 'top') {
        const inner = largestScrollableElement()
        if (inner) {
          const beforeInner = inner.scrollTop
          const down = payload.to === 'bottom' || direction !== 'up'
          const step =
            payload.to === 'bottom'
              ? inner.scrollHeight
              : typeof payload.y === 'number'
                ? payload.y
                : typeof amount === 'number' && Number.isFinite(amount)
                  ? amount
                  : Math.round(inner.clientHeight * 0.85)
          inner.scrollBy({ top: down ? step : -step, behavior: 'auto' })
          await waitForStableDom(800, 100)
          if (Math.abs(inner.scrollTop - beforeInner) >= 2) {
            target = 'inner'
            delta = inner.scrollTop - beforeInner
            atBottom = inner.scrollTop + inner.clientHeight >= inner.scrollHeight - 4
          } else {
            target = 'none'
          }
        }
      }

      return {
        scrollY: window.scrollY,
        atBottom,
        target,
        delta,
      }
    }

    function startElementPick(): void {
      cancelCrop?.()
      cancelPick?.()
      let highlighted: HTMLElement | undefined
      const hint = document.createElement('div')
      hint.textContent = '点击页面上要解释的按钮或文字 · Esc 取消'
      Object.assign(hint.style, {
        position: 'fixed',
        top: '12px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: '2147483647',
        pointerEvents: 'none',
        padding: '8px 14px',
        borderRadius: '999px',
        background: 'rgba(15,23,42,0.92)',
        color: '#f8fafc',
        font: '12px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
      })
      document.documentElement.appendChild(hint)
      const clearHighlight = () => {
        if (highlighted) highlighted.style.outline = ''
        highlighted = undefined
      }
      const candidate = (target: EventTarget | null): HTMLElement | undefined => {
        if (!(target instanceof Element)) return undefined
        return (target.closest(INTERACTIVE) ?? target) as HTMLElement
      }
      const onMove = (event: MouseEvent) => {
        const next = candidate(event.target)
        if (next === highlighted) return
        clearHighlight()
        highlighted = next
        if (highlighted) highlighted.style.outline = '3px solid #3b82f6'
      }
      const flash = (element: HTMLElement) => {
        const rect = element.getBoundingClientRect()
        const box = document.createElement('div')
        Object.assign(box.style, {
          position: 'fixed',
          left: `${rect.left}px`,
          top: `${rect.top}px`,
          width: `${rect.width}px`,
          height: `${rect.height}px`,
          border: '2px solid #22c55e',
          background: 'rgba(34,197,94,0.18)',
          borderRadius: '4px',
          pointerEvents: 'none',
          zIndex: '2147483647',
          transition: 'opacity 500ms ease, transform 500ms ease',
        })
        document.documentElement.appendChild(box)
        requestAnimationFrame(() => {
          box.style.opacity = '0'
          box.style.transform = 'scale(1.04)'
        })
        window.setTimeout(() => box.remove(), 520)
      }
      const onClick = (event: MouseEvent) => {
        const element = candidate(event.target)
        if (!element) return
        event.preventDefault()
        event.stopPropagation()
        flash(element)
        const rect = element.getBoundingClientRect()
        const result = {
          selector: selectorFor(element),
          title: titleForElement(element),
          tag: element.tagName.toLowerCase(),
          text: (element.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 240),
          rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
        }
        cancelPick?.()
        void safeRuntimeSendMessage({ type: 'NAVIFORGE_ELEMENT_PICKED', result })
      }
      const onKey = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          cancelPick?.()
          void safeRuntimeSendMessage({ type: 'NAVIFORGE_ELEMENT_PICK_CANCELLED' })
        }
      }
      cancelPick = () => {
        document.removeEventListener('mousemove', onMove, true)
        document.removeEventListener('click', onClick, true)
        window.removeEventListener('keydown', onKey, true)
        clearHighlight()
        hint.remove()
        cancelPick = undefined
      }
      document.addEventListener('mousemove', onMove, true)
      document.addEventListener('click', onClick, true)
      window.addEventListener('keydown', onKey, true)
    }

    function showOcrHud(payload: { phase?: string; text?: string; path?: string }): void {
      document.getElementById('naviforge-ocr-hud')?.remove()
      const root = document.createElement('div')
      root.id = 'naviforge-ocr-hud'
      root.setAttribute('data-naviforge-ocr-hud', '1')
      root.style.cssText = [
        'position:fixed',
        'z-index:2147483647',
        'top:16px',
        'right:16px',
        'width:min(420px,calc(100vw - 32px))',
        'max-height:min(70vh,560px)',
        'display:flex',
        'flex-direction:column',
        'gap:8px',
        'padding:12px 14px',
        'background:#111',
        'color:#fff',
        'font:13px/1.45 system-ui,sans-serif',
        'border-radius:10px',
        'box-shadow:0 8px 24px rgba(0,0,0,.28)',
      ].join(';')
      const title = document.createElement('div')
      title.style.cssText = 'font-weight:650'
      const body = document.createElement('pre')
      body.style.cssText =
        'margin:0;overflow:auto;white-space:pre-wrap;word-break:break-word;font:12px/1.45 ui-monospace,monospace;flex:1'
      if (payload.phase === 'working') {
        title.textContent = '正在识别文字…'
        body.textContent = '框选已完成，正在把截图发给 OCR 模型。'
      } else if (payload.phase === 'error') {
        title.textContent = '识别失败'
        body.textContent = payload.text || '未知错误'
      } else {
        title.textContent = '识别结果'
        body.textContent = payload.text || '（没有识别到文字）'
      }
      root.append(title, body)
      if (payload.path) {
        const path = document.createElement('div')
        path.textContent = `已保存 ${payload.path}`
        path.style.cssText = 'color:#bbb;font-size:11px'
        root.append(path)
      }
      const row = document.createElement('div')
      row.style.cssText = 'display:flex;gap:8px;justify-content:flex-end'
      if (payload.phase === 'result' && payload.text) {
        const copy = document.createElement('button')
        copy.type = 'button'
        copy.textContent = '复制'
        copy.style.cssText =
          'border:0;border-radius:6px;padding:6px 10px;background:#70a91d;color:#111;font:650 12px system-ui;cursor:pointer'
        copy.addEventListener('click', () => {
          void navigator.clipboard.writeText(payload.text ?? '').then(() => {
            copy.textContent = '已复制'
          })
        })
        row.append(copy)
      }
      const close = document.createElement('button')
      close.type = 'button'
      close.textContent = '关闭'
      close.style.cssText =
        'border:0;border-radius:6px;padding:6px 10px;background:#333;color:#fff;font:650 12px system-ui;cursor:pointer'
      const dismiss = () => root.remove()
      close.addEventListener('click', dismiss)
      row.append(close)
      root.append(row)
      document.documentElement.appendChild(root)
      if (payload.phase === 'error') {
        setTimeout(() => {
          if (root.isConnected) root.remove()
        }, 8000)
      }
    }

    function startRegionCrop(options?: { hint?: string }): Promise<{
      success: boolean
      cancelled?: boolean
      rect?: { x: number; y: number; width: number; height: number }
      devicePixelRatio?: number
      error?: string
    }> {
      cancelPick?.()
      cancelCrop?.()
      document.getElementById('naviforge-ocr-hud')?.remove()
      return new Promise((resolve) => {
        const root = document.createElement('div')
        root.setAttribute('data-naviforge-crop', '1')
        root.style.cssText = [
          'position:fixed',
          'inset:0',
          'z-index:2147483646',
          'cursor:crosshair',
          'background:rgba(15,23,20,.22)',
          'touch-action:none',
        ].join(';')
        const hint = document.createElement('div')
        hint.textContent = options?.hint ?? '按住拖动选择识别区域 · Esc 取消'
        hint.style.cssText =
          'position:fixed;top:16px;left:50%;transform:translateX(-50%);padding:8px 12px;background:#111;color:#fff;font:13px/1.4 system-ui,sans-serif;border-radius:8px;pointer-events:none'
        const box = document.createElement('div')
        box.style.cssText =
          'position:fixed;border:2px solid #70a91d;background:rgba(112,169,29,.15);pointer-events:none;display:none'
        root.append(hint, box)
        document.documentElement.appendChild(root)

        let startX = 0
        let startY = 0
        let dragging = false
        let settled = false

        const finish = (result: {
          success: boolean
          cancelled?: boolean
          rect?: { x: number; y: number; width: number; height: number }
          devicePixelRatio?: number
          error?: string
        }) => {
          if (settled) return
          settled = true
          window.removeEventListener('keydown', onKey, true)
          root.remove()
          cancelCrop = undefined
          resolve(result)
        }

        const onKey = (event: KeyboardEvent) => {
          if (event.key !== 'Escape') return
          event.preventDefault()
          event.stopPropagation()
          finish({ success: true, cancelled: true })
        }
        const paint = (x: number, y: number) => {
          const left = Math.min(startX, x)
          const top = Math.min(startY, y)
          box.style.left = `${left}px`
          box.style.top = `${top}px`
          box.style.width = `${Math.abs(x - startX)}px`
          box.style.height = `${Math.abs(y - startY)}px`
        }
        const onMove = (event: PointerEvent) => {
          if (!dragging) return
          paint(event.clientX, event.clientY)
        }
        const onUp = (event: PointerEvent) => {
          if (!dragging) return
          dragging = false
          try {
            root.releasePointerCapture(event.pointerId)
          } catch {
            // already released
          }
          const width = Math.abs(event.clientX - startX)
          const height = Math.abs(event.clientY - startY)
          if (width < 8 || height < 8) {
            hint.textContent = '选区太小，按住再拖一次 · Esc 取消'
            box.style.display = 'none'
            return
          }
          finish({
            success: true,
            rect: {
              x: Math.min(startX, event.clientX),
              y: Math.min(startY, event.clientY),
              width,
              height,
            },
            devicePixelRatio: window.devicePixelRatio || 1,
          })
        }

        root.addEventListener(
          'pointerdown',
          (event) => {
            event.preventDefault()
            event.stopPropagation()
            dragging = true
            startX = event.clientX
            startY = event.clientY
            box.style.display = 'block'
            paint(startX, startY)
            hint.textContent = '松开完成框选 · Esc 取消'
            try {
              root.setPointerCapture(event.pointerId)
            } catch {
              // capture not available
            }
          },
          true
        )
        root.addEventListener('pointermove', onMove, true)
        root.addEventListener('pointerup', onUp, true)
        root.addEventListener('pointercancel', onUp, true)
        window.addEventListener('keydown', onKey, true)
        cancelCrop = () => finish({ success: true, cancelled: true })
      })
    }

    const pageControlCtx: PageControlContext = {
      revision: revisionRef,
      TOP_COLORS,
      marks,
      pageSelectionText,
      startElementPick,
      startRegionCrop,
      showOcrHud,
      getPc,
      entriesFromSelectorMapLocal,
      elementForIndex,
      selectorFor,
      bindSync,
      placeMark,
      scheduleSync,
      runExtract,
      reportPayload,
      clearMarks,
      selectorEntries,
      markInViewport,
      watchMarksStale,
      hideCaptureChrome,
      restoreCaptureChrome,
      performAgentScroll,
    }

    installPageControlListener(async (action, payload, sendResponse) => {
      try {
        await dispatchPageControl(pageControlCtx, action, payload, sendResponse)
      } catch (e) {
        sendResponse({ success: false, error: (e as Error).message })
      }
    })

    let myTabId: number | null = null
    let presenceTimer: number | null = null

    function teardownStaleExtensionContext(): void {
      if (presenceTimer != null) {
        clearInterval(presenceTimer)
        presenceTimer = null
      }
      runIfExtensionAlive(() => chrome.storage.onChanged.removeListener(onPresenceStorage))
    }
    teardownPresence = teardownStaleExtensionContext

    async function syncPresence(raw?: unknown): Promise<void> {
      if (!extensionRuntimeAlive()) {
        teardownStaleExtensionContext()
        return
      }
      try {
        const value =
          raw ??
          (await safeStorageLocalGet(STORAGE.agentPresence))?.[STORAGE.agentPresence]
        if (!extensionRuntimeAlive()) {
          teardownStaleExtensionContext()
          return
        }
        const presence = parseAgentPresence(value)
        if (myTabId == null) return
        const live = isPresenceLive(presence, myTabId)
        await setAgentLive(live, presence?.action)
      } catch (error) {
        if (isExtensionContextInvalidated(error)) teardownStaleExtensionContext()
      }
    }

    function onPresenceStorage(
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ): void {
      if (area !== 'local' || !changes[STORAGE.agentPresence]) return
      if (!extensionRuntimeAlive()) {
        teardownStaleExtensionContext()
        return
      }
      void syncPresence(changes[STORAGE.agentPresence].newValue)
    }

    void safeRuntimeSendMessage<{ tabId?: number | null }>({
      type: 'PAGE_CONTROL',
      action: 'get_my_tab_id',
    })
      .then((response) => {
        if (!extensionRuntimeAlive()) {
          teardownStaleExtensionContext()
          return
        }
        myTabId = typeof response?.tabId === 'number' ? response.tabId : null
        return syncPresence()
      })
      .catch((error) => {
        if (isExtensionContextInvalidated(error)) teardownStaleExtensionContext()
      })

    if (extensionRuntimeAlive()) {
      runIfExtensionAlive(() => chrome.storage.onChanged.addListener(onPresenceStorage))
      presenceTimer = window.setInterval(() => {
        void syncPresence()
      }, 2_000)
    }

    window.addEventListener('pagehide', () => {
      removeContextGuard()
      teardownStaleExtensionContext()
    })
  },
})
