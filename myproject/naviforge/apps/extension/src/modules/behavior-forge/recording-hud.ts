import type { RecordingHudCopy } from './recording-hud-copy.js'

const ROOT_ID = 'naviforge-behavior-recording-hud'
const STYLE_ID = 'naviforge-behavior-recording-hud-style'

export type RecordingHudPhase = 'idle' | 'recording' | 'saving' | 'saved' | 'error'

export type RecordingHudState = {
  phase: RecordingHudPhase
  recording: boolean
  eventCount: number
  savedCount?: number | null
  error?: string
  pageUrl?: string
  pageTitle?: string
}

type Hooks = {
  onStart: () => void
  onStop: () => void
  onViewReplay: () => void
  onClose: () => void
  onRecordAgain: () => void
}

type HudHooks = Hooks & {
  onPoll?: () => void
  onPosition?: (x: number, y: number) => void
}

let pollTimer: ReturnType<typeof setInterval> | null = null
let activeCopy: RecordingHudCopy | null = null
let activeState: RecordingHudState | null = null
let activeHooks: HudHooks | null = null

function ensureStyles(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
    #${ROOT_ID} {
      --br-text: #f6f2e8;
      --br-muted: rgba(246,242,232,.62);
      --br-accent: #e85d4c;
      --br-ok: #7cb342;
    }
    #${ROOT_ID} .br-btn {
      border: 0; cursor: pointer; font: inherit; color: inherit;
      transition: transform .12s ease, opacity .12s ease;
    }
    #${ROOT_ID} .br-btn:active { transform: scale(.97); }
    #${ROOT_ID} .br-btn:disabled { opacity: .45; cursor: not-allowed; }
    #${ROOT_ID} .br-record {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      width: 100%; border-radius: 12px; padding: 11px 14px; font-weight: 700; font-size: 13px;
    }
    #${ROOT_ID} .br-record-idle {
      background: linear-gradient(135deg, #e85d4c, #c9453a); color: #fff;
      box-shadow: 0 8px 24px rgba(232,93,76,.35);
    }
    #${ROOT_ID} .br-record-active {
      background: rgba(255,255,255,.08); color: var(--br-text); border: 1px solid rgba(232,93,76,.55);
    }
    #${ROOT_ID} .br-dot {
      width: 8px; height: 8px; border-radius: 50%; background: var(--br-accent);
      animation: br-pulse 1.4s ease-in-out infinite; flex-shrink: 0;
    }
    @keyframes br-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(232,93,76,.45); }
      50% { box-shadow: 0 0 0 6px rgba(232,93,76,0); }
    }
    #${ROOT_ID} .br-result {
      margin-top: 10px; padding: 10px; border-radius: 12px;
      background: rgba(124,179,66,.12); border: 1px solid rgba(124,179,66,.32);
    }
    #${ROOT_ID} .br-result.br-result-error {
      background: rgba(232,93,76,.12); border-color: rgba(232,93,76,.35);
    }
    #${ROOT_ID} .br-result-error .br-result-title { color: #ffc9c0; }
    #${ROOT_ID} .br-result-title {
      font-size: 12px; font-weight: 700; color: #dff0c8; margin-bottom: 4px;
    }
    #${ROOT_ID} .br-result-hint {
      font-size: 10px; color: var(--br-muted); line-height: 1.45; margin-bottom: 8px;
    }
    #${ROOT_ID} .br-result-actions { display: flex; flex-direction: column; gap: 6px; }
    #${ROOT_ID} .br-replay-btn {
      width: 100%; border-radius: 10px; padding: 9px 12px; font-size: 12px; font-weight: 700;
      background: #5a7a2a; color: #fff; border: 0; cursor: pointer;
    }
    #${ROOT_ID} .br-again-btn {
      width: 100%; border-radius: 8px; padding: 7px; font-size: 10px;
      background: transparent; color: var(--br-muted); border: 1px solid rgba(255,255,255,.14);
      cursor: pointer;
    }
    #${ROOT_ID} .br-icon-btn {
      width: 28px; height: 28px; border-radius: 8px; background: rgba(255,255,255,.08);
      display: inline-flex; align-items: center; justify-content: center; color: var(--br-text);
      border: 0; cursor: pointer; flex-shrink: 0;
    }
    #${ROOT_ID} .br-drag { cursor: grab; user-select: none; }
    #${ROOT_ID} .br-drag:active { cursor: grabbing; }
    #${ROOT_ID} .br-page {
      margin-bottom: 8px; padding: 8px 10px; border-radius: 10px;
      background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1);
    }
    #${ROOT_ID} .br-page-label {
      font-size: 9px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
      color: var(--br-accent); margin-bottom: 3px;
    }
    #${ROOT_ID} .br-page-title {
      font-size: 12px; font-weight: 600; line-height: 1.3;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    #${ROOT_ID} .br-page-url {
      font-size: 10px; color: var(--br-muted); margin-top: 2px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    #${ROOT_ID} .br-body { padding: 0 12px 12px; }
  `
  document.head.appendChild(style)
}

function applyState(root: HTMLElement, copy: RecordingHudCopy, state: RecordingHudState): void {
  activeCopy = copy
  activeState = state

  const toggleBtn = root.querySelector('[data-br-toggle]') as HTMLButtonElement | null
  const statusEl = root.querySelector('[data-br-status]')
  const resultWrap = root.querySelector('[data-br-result]') as HTMLElement | null
  const resultTitle = root.querySelector('[data-br-result-title]')
  const resultHint = root.querySelector('[data-br-result-hint]')
  const closeBtn = root.querySelector('[data-br-close]') as HTMLButtonElement | null
  const toggleWrap = root.querySelector('[data-br-toggle-wrap]') as HTMLElement | null

  const saving = state.phase === 'saving'
  const saved = state.phase === 'saved'
  const errored = state.phase === 'error'
  const recording = state.recording || state.phase === 'recording'
  const showToggle = !saved && !saving && !errored

  if (toggleWrap) toggleWrap.style.display = showToggle ? 'block' : 'none'

  if (toggleBtn) {
    toggleBtn.disabled = saving
    if (recording) {
      toggleBtn.className = 'br-btn br-record br-record-active'
      toggleBtn.innerHTML = `<span class="br-dot"></span><span>${copy.stop}</span><span style="margin-left:auto;font-size:11px;opacity:.7;font-weight:600">${state.eventCount}</span>`
    } else {
      toggleBtn.className = 'br-btn br-record br-record-idle'
      toggleBtn.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:#fff;flex-shrink:0"></span><span>${copy.start}</span>`
    }
  }

  if (statusEl) {
    if (saving) statusEl.textContent = copy.saving
    else if (saved || errored) statusEl.textContent = ''
    else if (recording) statusEl.textContent = copy.recording.replace('{count}', String(state.eventCount))
    else statusEl.textContent = copy.hint
  }

  if (resultWrap && resultTitle && resultHint) {
    if (saved) {
      resultWrap.style.display = 'block'
      resultWrap.classList.remove('br-result-error')
      const count = state.savedCount ?? 0
      resultTitle.textContent =
        count > 0 ? copy.saved.replace('{count}', String(count)) : copy.savedEmpty
      resultHint.textContent = copy.whereReplay
    } else if (errored) {
      resultWrap.style.display = 'block'
      resultWrap.classList.add('br-result-error')
      resultTitle.textContent = state.error ?? copy.error
      resultHint.textContent = copy.errorHint
    } else {
      resultWrap.style.display = 'none'
      resultWrap.classList.remove('br-result-error')
    }
  }

  if (closeBtn) closeBtn.disabled = recording || saving

  const replayBtn = root.querySelector('[data-br-replay]') as HTMLButtonElement | null
  const againBtn = root.querySelector('[data-br-again]') as HTMLButtonElement | null
  if (replayBtn) replayBtn.style.display = saved || errored ? 'block' : 'none'
  if (againBtn) againBtn.style.display = saved || errored ? 'block' : 'none'

  const pageWrap = root.querySelector('[data-br-page]') as HTMLElement | null
  const pageTitleEl = root.querySelector('[data-br-page-title]')
  const pageUrlEl = root.querySelector('[data-br-page-url]')
  if (pageWrap && pageTitleEl && pageUrlEl) {
    const showPage = recording && Boolean(state.pageTitle || state.pageUrl)
    pageWrap.style.display = showPage ? 'block' : 'none'
    if (showPage) {
      pageTitleEl.textContent = state.pageTitle || copy.recordingPage
      pageUrlEl.textContent = state.pageUrl ? shortenUrl(state.pageUrl) : ''
      pageUrlEl.setAttribute('title', state.pageUrl ?? '')
    }
  }
}

function shortenUrl(url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname === '/' ? '' : u.pathname
    const text = `${u.hostname}${path}`
    return text.length > 42 ? `${text.slice(0, 39)}…` : text
  } catch {
    return url.length > 42 ? `${url.slice(0, 39)}…` : url
  }
}

function applyPosition(root: HTMLElement, pos: { x: number; y: number }): void {
  const maxX = Math.max(8, window.innerWidth - root.offsetWidth - 8)
  const maxY = Math.max(8, window.innerHeight - root.offsetHeight - 8)
  const x = Math.min(Math.max(8, pos.x), maxX)
  const y = Math.min(Math.max(8, pos.y), maxY)
  root.style.left = `${x}px`
  root.style.top = `${y}px`
  root.style.right = 'auto'
  root.style.bottom = 'auto'
}

function defaultBottomRight(root: HTMLElement): void {
  root.style.right = '20px'
  root.style.bottom = 'max(16px, env(safe-area-inset-bottom, 0px))'
  root.style.left = 'auto'
  root.style.top = 'auto'
}

function makeDraggable(
  root: HTMLElement,
  handle: HTMLElement,
  onPosition?: (x: number, y: number) => void
): void {
  let dragging = false
  let startX = 0
  let startY = 0
  let originX = 0
  let originY = 0

  handle.addEventListener('pointerdown', (e) => {
    if ((e.target as HTMLElement).closest('button')) return
    dragging = true
    startX = e.clientX
    startY = e.clientY
    const rect = root.getBoundingClientRect()
    originX = rect.left
    originY = rect.top
    handle.setPointerCapture(e.pointerId)
  })
  handle.addEventListener('pointermove', (e) => {
    if (!dragging) return
    const x = Math.max(8, Math.min(window.innerWidth - root.offsetWidth - 8, originX + e.clientX - startX))
    const y = Math.max(8, Math.min(window.innerHeight - root.offsetHeight - 8, originY + e.clientY - startY))
    root.style.left = `${x}px`
    root.style.top = `${y}px`
    root.style.right = 'auto'
    root.style.bottom = 'auto'
  })
  const stop = (e?: PointerEvent) => {
    if (dragging && onPosition) {
      const rect = root.getBoundingClientRect()
      onPosition(rect.left, rect.top)
    }
    dragging = false
    if (e) handle.releasePointerCapture(e.pointerId)
  }
  handle.addEventListener('pointerup', (e) => stop(e))
  handle.addEventListener('pointercancel', (e) => stop(e))
}

function bindDelegatedEvents(root: HTMLElement): void {
  if (root.dataset.brBound === '1') return
  root.dataset.brBound = '1'

  root.addEventListener('click', (e) => {
    const target = e.target as HTMLElement
    if (target.closest('[data-br-toggle]')) {
      if (!activeState || activeState.phase === 'saving') return
      if (activeState.recording) activeHooks?.onStop()
      else activeHooks?.onStart()
      return
    }
    if (target.closest('[data-br-close]')) {
      if (!activeState || activeState.recording || activeState.phase === 'saving') return
      activeHooks?.onClose()
      return
    }
    if (target.closest('[data-br-replay]')) {
      activeHooks?.onViewReplay()
      return
    }
    if (target.closest('[data-br-again]')) {
      activeHooks?.onRecordAgain()
    }
  })
}

function ensurePoll(hooks: HudHooks): void {
  if (!hooks.onPoll) return
  if (!pollTimer) {
    pollTimer = setInterval(() => activeHooks?.onPoll?.(), 1500)
  }
}

export function hideBehaviorRecordingHud(): void {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  activeHooks = null
  activeCopy = null
  activeState = null
  document.getElementById(ROOT_ID)?.remove()
}

export function isBehaviorRecordingHudVisible(): boolean {
  return Boolean(document.getElementById(ROOT_ID))
}

export function showBehaviorRecordingHud(
  copy: RecordingHudCopy,
  state: RecordingHudState,
  hooks: HudHooks,
  opts?: { pos?: { x: number; y: number } | null }
): void {
  ensureStyles()
  activeHooks = hooks

  const existing = document.getElementById(ROOT_ID)
  if (existing) {
    applyState(existing, copy, state)
    if (opts?.pos) applyPosition(existing, opts.pos)
    ensurePoll(hooks)
    return
  }

  const root = document.createElement('div')
  root.id = ROOT_ID
  root.setAttribute('data-naviforge-behavior-recording-hud', '1')
  root.style.cssText = [
    'position:fixed',
    'right:20px',
    'bottom:max(16px, env(safe-area-inset-bottom, 0px))',
    'z-index:2147483645',
    'width:min(292px,calc(100vw - 24px))',
    'max-height:calc(100vh - 24px)',
    'overflow:auto',
    'border-radius:16px',
    'background:linear-gradient(160deg,rgba(26,24,20,.97),rgba(18,16,14,.98))',
    'border:1px solid rgba(255,255,255,.14)',
    'box-shadow:0 20px 48px rgba(0,0,0,.42)',
    'color:var(--br-text,#f6f2e8)',
    'font:12px/1.4 system-ui,-apple-system,sans-serif',
    'backdrop-filter:blur(18px)',
    'user-select:none',
  ].join(';')

  root.innerHTML = `
    <div data-br-drag class="br-drag" style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px 6px;gap:8px" title="${copy.dragHint}">
      <div style="font-size:10px;font-weight:700;letter-spacing:.12em;opacity:.88;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">● ${copy.title}</div>
      <button type="button" class="br-icon-btn" data-br-close title="${copy.close}">✕</button>
    </div>
    <div class="br-body">
      <div data-br-page class="br-page" style="display:none">
        <div class="br-page-label">${copy.recordingPage}</div>
        <div data-br-page-title class="br-page-title"></div>
        <div data-br-page-url class="br-page-url"></div>
      </div>
      <div data-br-status style="font-size:10px;color:var(--br-muted);margin-bottom:8px;min-height:14px"></div>
      <div data-br-toggle-wrap>
        <button type="button" class="br-btn br-record br-record-idle" data-br-toggle></button>
      </div>
      <div data-br-result style="display:none" class="br-result">
        <div data-br-result-title class="br-result-title"></div>
        <div data-br-result-hint class="br-result-hint"></div>
        <div class="br-result-actions">
          <button type="button" class="br-replay-btn" data-br-replay>${copy.viewReplay}</button>
          <button type="button" class="br-again-btn" data-br-again>${copy.recordAgain}</button>
        </div>
      </div>
    </div>
  `

  document.documentElement.append(root)
  bindDelegatedEvents(root)
  applyState(root, copy, state)

  const drag = root.querySelector('[data-br-drag]') as HTMLElement
  makeDraggable(root, drag, (x, y) => hooks.onPosition?.(x, y))

  if (opts?.pos) applyPosition(root, opts.pos)
  else defaultBottomRight(root)

  ensurePoll(hooks)
}

export function updateBehaviorRecordingHud(copy: RecordingHudCopy, state: RecordingHudState): void {
  const root = document.getElementById(ROOT_ID)
  if (!root) return
  applyState(root, copy, state)
}
