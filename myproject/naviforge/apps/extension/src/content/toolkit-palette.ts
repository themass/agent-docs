import {
  TOOLKIT_CATALOG,
  type ToolkitCatalogId,
  type ToolkitCatalogItem,
} from '../lib/toolkit-catalog'
import { TOOLKIT_PALETTE_RUN } from '../lib/toolkit-palette-runner'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'
import { isNewApiLoggedIn, loadNewApiAuth } from '../lib/newapi-auth'
import {
  initPaletteI18n,
  paletteFooterHint,
  paletteFooterKeys,
  paletteSearchPlaceholder,
  toolkitI18n,
  toolkitSectionLabel,
} from '../lib/palette-i18n'
import { t } from '../i18n/t'

const ROOT_ID = 'naviforge-toolkit-palette'

const HIDDEN_IN_PALETTE = new Set<ToolkitCatalogId>(['page-toollist', 'account'])

async function runPaletteAction(id: ToolkitCatalogId): Promise<void> {
  const result = (await safeRuntimeSendMessage({
    type: TOOLKIT_PALETTE_RUN,
    toolId: id,
  })) as { ok?: boolean; error?: string; cancelled?: boolean } | undefined
  if (result?.cancelled) return
  if (result && result.ok === false && result.error) {
    window.alert(result.error)
  }
}

function closePalette(root: HTMLElement): void {
  root.remove()
}

export function showToolkitPalette(): void {
  void showToolkitPaletteInner()
}

async function showToolkitPaletteInner(): Promise<void> {
  await initPaletteI18n()
  document.getElementById(ROOT_ID)?.remove()

  const root = document.createElement('div')
  root.id = ROOT_ID
  root.setAttribute('data-naviforge-toolkit-palette', '1')
  root.style.cssText = [
    'position:fixed',
    'inset:0',
    'z-index:2147483647',
    'display:flex',
    'align-items:flex-start',
    'justify-content:center',
    'padding:48px 16px 16px',
    'background:rgba(15,20,18,.45)',
    'font:13px/1.45 system-ui,-apple-system,sans-serif',
  ].join(';')

  const panel = document.createElement('div')
  panel.style.cssText = [
    'width:min(400px,100%)',
    'max-height:min(72vh,640px)',
    'display:flex',
    'flex-direction:column',
    'border-radius:16px',
    'background:#f7f8f7',
    'color:#0f1412',
    'box-shadow:0 24px 64px rgba(0,0,0,.28)',
    'border:1px solid rgba(15,20,18,.08)',
    'overflow:hidden',
  ].join(';')

  const searchWrap = document.createElement('div')
  searchWrap.style.cssText = 'padding:12px 12px 8px;border-bottom:1px solid rgba(15,20,18,.08)'
  const search = document.createElement('input')
  search.type = 'search'
  search.placeholder = paletteSearchPlaceholder()
  search.autocomplete = 'off'
  search.style.cssText = [
    'width:100%',
    'box-sizing:border-box',
    'border:0',
    'border-radius:10px',
    'padding:10px 12px',
    'background:#fff',
    'font:inherit',
    'outline:2px solid transparent',
  ].join(';')
  searchWrap.append(search)

  const list = document.createElement('div')
  list.style.cssText = 'flex:1;overflow:auto;padding:4px 8px 8px'

  const footer = document.createElement('div')
  footer.style.cssText =
    'padding:8px 12px 10px;border-top:1px solid rgba(15,20,18,.08);font-size:11px;color:#5c6b62;display:flex;justify-content:space-between;gap:8px'
  footer.innerHTML = `<span>${paletteFooterKeys()}</span><span>${paletteFooterHint()}</span>`

  const authBar = document.createElement('div')
  authBar.style.cssText = 'padding:6px 12px 0;border-top:1px solid rgba(15,20,18,.08)'
  footer.before(authBar)

  async function paintAuthBar(): Promise<void> {
    authBar.textContent = ''
    const loginBtn = document.createElement('button')
    loginBtn.type = 'button'
    loginBtn.style.cssText = [
      'display:flex',
      'align-items:center',
      'gap:6px',
      'width:100%',
      'border:0',
      'border-radius:8px',
      'padding:5px 8px',
      'background:transparent',
      'cursor:pointer',
      'text-align:left',
      'font:inherit',
      'font-size:10px',
      'color:#5c6b62',
    ].join(';')
    const auth = await loadNewApiAuth()
    const manual = auth.mode === 'manual'
    const loggedIn = !manual && isNewApiLoggedIn(auth)
    const label = document.createElement('span')
    label.style.cssText = 'min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600;color:#0f1412'
    const meta = document.createElement('span')
    meta.style.cssText = 'flex-shrink:0;font-variant-numeric:tabular-nums;opacity:.85'
    if (manual) {
      label.textContent = t('authBar.manualMode')
      meta.textContent = ''
    } else if (loggedIn) {
      label.textContent = auth.user?.displayName || auth.user?.email || 'NewAPI'
      meta.textContent =
        typeof auth.user?.quotaUsd === 'number' ? `$${auth.user.quotaUsd.toFixed(2)}` : ''
      loginBtn.style.color = '#3a5a1a'
    } else {
      label.textContent = t('authBar.signIn')
      meta.textContent = ''
    }
    loginBtn.title = manual
      ? t('authBar.manualHint')
      : loggedIn
        ? auth.user?.quotaUsd != null
          ? t('authBar.quota', { amount: `$${auth.user.quotaUsd.toFixed(2)}` })
          : t('authBar.connected')
        : t('authBar.signInHint')
    loginBtn.append(label, meta)
    loginBtn.addEventListener('click', () => {
      closePalette(root)
      void safeRuntimeSendMessage({ type: TOOLKIT_PALETTE_RUN, toolId: 'account' })
    })
    authBar.append(loginBtn)
  }

  void paintAuthBar()

  panel.append(searchWrap, list, authBar, footer)
  root.append(panel)
  document.documentElement.append(root)

  const sections: ToolkitCatalogItem['section'][] = ['quick', 'capture', 'page', 'utility']
  let activeIndex = 0
  const rowEls: HTMLButtonElement[] = []

  function render(filter = ''): void {
    list.textContent = ''
    rowEls.length = 0
    activeIndex = 0
    const q = filter.trim().toLowerCase()
    for (const section of sections) {
      const items = TOOLKIT_CATALOG.filter((item) => {
        if (HIDDEN_IN_PALETTE.has(item.id)) return false
        if (item.section !== section) return false
        if (!q) return true
        const { label, hint } = toolkitI18n(item.id)
        return label.toLowerCase().includes(q) || hint.toLowerCase().includes(q)
      })
      if (!items.length) continue

      const heading = document.createElement('div')
      heading.textContent = toolkitSectionLabel(section)
      heading.style.cssText =
        'padding:6px 8px 4px;font-size:11px;font-weight:650;color:#5c6b62;text-transform:uppercase;letter-spacing:.04em'
      list.append(heading)

      for (const item of items) {
        const btn = document.createElement('button')
        btn.type = 'button'
        btn.dataset.toolId = item.id
        btn.style.cssText = [
          'display:flex',
          'align-items:center',
          'justify-content:space-between',
          'gap:10px',
          'width:100%',
          'border:0',
          'border-radius:10px',
          'padding:8px 10px',
          'background:transparent',
          'cursor:pointer',
          'text-align:left',
        ].join(';')
        const { label, hint } = toolkitI18n(item.id)
        const left = document.createElement('div')
        left.innerHTML = `<div style="font-weight:600;font-size:13px">${label}</div><div style="font-size:11px;color:#5c6b62;margin-top:1px">${hint}</div>`
        const right = document.createElement('span')
        right.textContent = item.shortcut ?? ''
        right.style.cssText = 'font-size:11px;color:#8a958c;font-variant-numeric:tabular-nums'
        btn.append(left, right)
        btn.addEventListener('click', () => {
          closePalette(root)
          void runPaletteAction(item.id)
        })
        btn.addEventListener('mouseenter', () => {
          activeIndex = rowEls.indexOf(btn)
          paintActive()
        })
        list.append(btn)
        rowEls.push(btn)
      }
    }
    paintActive()
  }

  function paintActive(): void {
    for (let i = 0; i < rowEls.length; i++) {
      const el = rowEls[i]!
      el.style.background = i === activeIndex ? 'rgba(112,169,29,.18)' : 'transparent'
    }
  }

  search.addEventListener('input', () => render(search.value))
  search.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      activeIndex = Math.min(activeIndex + 1, rowEls.length - 1)
      paintActive()
      rowEls[activeIndex]?.scrollIntoView({ block: 'nearest' })
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      activeIndex = Math.max(activeIndex - 1, 0)
      paintActive()
      rowEls[activeIndex]?.scrollIntoView({ block: 'nearest' })
    } else if (event.key === 'Enter' && rowEls[activeIndex]) {
      event.preventDefault()
      const id = rowEls[activeIndex].dataset.toolId as ToolkitCatalogId
      closePalette(root)
      void runPaletteAction(id)
    }
  })

  const onKey = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      closePalette(root)
      window.removeEventListener('keydown', onKey, true)
    }
  }
  window.addEventListener('keydown', onKey, true)
  root.addEventListener('click', (event) => {
    if (event.target === root) closePalette(root)
  })

  render()
  search.focus()
}
