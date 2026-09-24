import { DEFAULT_HUD_PREFS, HUD_BASE_WIDTH, type GeniusFallHudPrefs, type GeniusFallHudState } from './hud-types.js'
import { isQuotaFallen } from './quota-fallen.js'

const ROOT_ID = 'naviforge-genius-fall-hud'
const STYLE_ID = 'naviforge-genius-fall-hud-style'

function ringColor(pct: number | null): string {
  if (pct == null) return '#9aa89a'
  if (pct >= 85) return '#ff5c6a'
  if (pct >= 60) return '#f5a623'
  return '#7cb342'
}

function formatUsd(n: number | null): string {
  if (n == null) return '—'
  if (n >= 1000) return `$${(n / 1000).toFixed(1)}k`
  return `$${n.toFixed(2)}`
}

function formatReset(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
  } catch {
    return '—'
  }
}

function daysUntilReset(iso: string | null): number | null {
  if (!iso) return null
  try {
    const end = new Date(iso).getTime()
    if (!Number.isFinite(end)) return null
    return Math.max(0, Math.ceil((end - Date.now()) / 86_400_000))
  } catch {
    return null
  }
}

function contrastTheme(bgColor: string, bgOpacity: number) {
  const { r, g, b } = hexToRgb(bgColor)
  const a = bgOpacity
  const br = r * a + 18 * (1 - a)
  const bg = g * a + 20 * (1 - a)
  const bb = b * a + 19 * (1 - a)
  const lum = (0.299 * br + 0.587 * bg + 0.114 * bb) / 255
  if (lum > 0.58) {
    return {
      text: '#17211f',
      muted: 'rgba(23,33,31,.72)',
      line: 'rgba(23,33,31,.14)',
      btn: 'rgba(23,33,31,.06)',
      btnHover: 'rgba(23,33,31,.12)',
      badge: 'rgba(112,169,29,.18)',
      badgeText: '#3a5a1a',
    }
  }
  return {
    text: '#f6f2e8',
    muted: 'rgba(246,242,232,.78)',
    line: 'rgba(255,255,255,.16)',
    btn: 'rgba(255,255,255,.1)',
    btnHover: 'rgba(255,255,255,.18)',
    badge: 'rgba(112,169,29,.28)',
    badgeText: '#dff0c8',
  }
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = Number.parseInt(full.slice(0, 6), 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

function bgStyle(prefs: GeniusFallHudPrefs): string {
  const { r, g, b } = hexToRgb(prefs.bgColor)
  const a = prefs.bgOpacity
  return `linear-gradient(155deg,rgba(${r},${g},${b},${a}) 0%,rgba(${Math.max(0, r - 18)},${Math.max(0, g - 18)},${Math.max(0, b - 18)},${Math.min(1, a + 0.02)}) 100%)`
}

function ensureStyles(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
    #${ROOT_ID} {
      --gf-text: #f6f2e8;
      --gf-muted: rgba(246,242,232,.62);
      --gf-line: rgba(255,255,255,.12);
      --gf-btn: rgba(255,255,255,.08);
      --gf-btn-hover: rgba(255,255,255,.16);
    }
    #${ROOT_ID} .gf-platform-btn {
      border: 1px solid var(--gf-line); background: var(--gf-btn); color: var(--gf-text);
      border-radius: 9px; padding: 4px 8px; font-size: 10px; font-weight: 650;
      cursor: pointer; white-space: nowrap;
    }
    #${ROOT_ID} .gf-platform-btn:hover { background: var(--gf-btn-hover); }
    #${ROOT_ID} .gf-reset-badge {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      margin: 8px 0 4px; padding: 8px 10px; border-radius: 10px;
      background: var(--gf-badge); border: 1px solid var(--gf-line);
    }
    #${ROOT_ID} .gf-reset-label { font-size: 10px; font-weight: 700; color: var(--gf-badge-text); letter-spacing: .04em; }
    #${ROOT_ID} .gf-reset-date { font-size: 15px; font-weight: 800; color: var(--gf-badge-text); font-variant-numeric: tabular-nums; }
    #${ROOT_ID} .gf-reset-sub { font-size: 9px; color: var(--gf-muted); margin-top: 2px; }
    #${ROOT_ID} .gf-title-main { font-size: 12px; font-weight: 800; line-height: 1.25; color: var(--gf-text); }
    #${ROOT_ID} .gf-title-sub { font-size: 9px; letter-spacing: .14em; font-weight: 650; color: var(--gf-muted); margin-top: 2px; }
    #${ROOT_ID} .gf-btn {
      border: 0; background: var(--gf-btn); color: var(--gf-text);
      border-radius: 9px; width: 28px; height: 28px; cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center;
      transition: background .15s ease, transform .15s ease;
    }
    #${ROOT_ID} .gf-btn:hover { background: var(--gf-btn-hover); }
    #${ROOT_ID} .gf-btn:active { transform: scale(.94); }
    #${ROOT_ID} .gf-btn[data-spin="1"] svg { animation: gf-spin .8s linear infinite; }
    @keyframes gf-spin { to { transform: rotate(360deg); } }
    #${ROOT_ID} .gf-drag { cursor: grab; }
    #${ROOT_ID} .gf-drag:active { cursor: grabbing; }
    #${ROOT_ID} .gf-pulse {
      width: 6px; height: 6px; border-radius: 50%; background: #f5d76e;
      box-shadow: 0 0 8px rgba(245,215,110,.7);
      animation: gf-pulse 2.4s ease-in-out infinite;
    }
    @keyframes gf-pulse {
      0%, 100% { opacity: .55; transform: scale(.9); }
      50% { opacity: 1; transform: scale(1.1); }
    }
    #${ROOT_ID} .gf-resize {
      position: absolute; right: 2px; bottom: 2px; width: 14px; height: 14px;
      cursor: nwse-resize; opacity: .45; border-radius: 0 0 10px 0;
    }
    #${ROOT_ID} .gf-resize:hover { opacity: .85; }
    #${ROOT_ID} .gf-resize::after {
      content: ''; position: absolute; right: 3px; bottom: 3px; width: 8px; height: 8px;
      border-right: 2px solid rgba(255,255,255,.7); border-bottom: 2px solid rgba(255,255,255,.7);
    }
    #${ROOT_ID}.gf-fallen {
      border-color: rgba(255, 92, 106, .55);
      box-shadow: 0 24px 60px rgba(120, 24, 24, .45), 0 0 0 1px rgba(255, 120, 120, .12) inset;
    }
    #${ROOT_ID} .gf-fallen-banner {
      display: none;
      margin: 0 0 10px;
      padding: 12px 10px;
      border-radius: 14px;
      text-align: center;
      background: linear-gradient(145deg, rgba(180, 40, 40, .28), rgba(80, 20, 20, .35));
      border: 1px solid rgba(255, 120, 120, .35);
      animation: gf-fallen-pop .55s cubic-bezier(.34, 1.4, .64, 1) both;
    }
    #${ROOT_ID}.gf-fallen .gf-fallen-banner { display: block; }
    #${ROOT_ID} .gf-fallen-emoji {
      font-size: 22px;
      line-height: 1.2;
      letter-spacing: .12em;
      animation: gf-fallen-wobble 2.8s ease-in-out infinite;
    }
    #${ROOT_ID} .gf-fallen-title {
      margin-top: 6px;
      font-size: 20px;
      font-weight: 900;
      letter-spacing: .08em;
      color: #ffd4d4;
      text-shadow: 0 2px 12px rgba(255, 80, 80, .45);
    }
    #${ROOT_ID} .gf-fallen-sub {
      margin-top: 4px;
      font-size: 10px;
      color: rgba(255, 220, 220, .78);
      line-height: 1.45;
    }
    #${ROOT_ID}.gf-fallen .gf-pulse {
      background: #ff5c6a;
      box-shadow: 0 0 10px rgba(255, 92, 106, .8);
      animation: gf-fallen-pulse 1.2s ease-in-out infinite;
    }
    @keyframes gf-fallen-pop {
      from { opacity: 0; transform: scale(.92) translateY(6px); }
      to { opacity: 1; transform: scale(1) translateY(0); }
    }
    @keyframes gf-fallen-wobble {
      0%, 100% { transform: rotate(-2deg); }
      50% { transform: rotate(2deg); }
    }
    @keyframes gf-fallen-pulse {
      0%, 100% { opacity: .7; transform: scale(.85); }
      50% { opacity: 1; transform: scale(1.15); }
    }
    #naviforge-gf-theme-pop {
      position: fixed; z-index: 2147483647;
      width: 168px; padding: 10px; border-radius: 12px;
      background: rgba(18,20,19,.98); border: 1px solid rgba(255,255,255,.18);
      box-shadow: 0 16px 40px rgba(0,0,0,.45);
      font: 11px/1.35 system-ui,sans-serif; color: #f6f2e8;
    }
    #naviforge-gf-theme-pop label { display: block; font-size: 9px; opacity: .7; margin-bottom: 4px; }
    #naviforge-gf-theme-pop input[type="color"] {
      width: 100%; height: 28px; border: 0; padding: 0; background: transparent; cursor: pointer;
    }
    #naviforge-gf-theme-pop input[type="range"] { width: 100%; }
  `
  document.head.appendChild(style)
}

function ringSvg(percent: number | null, size: number, stroke: number): string {
  const p = percent == null ? 0 : Math.min(100, Math.max(0, percent))
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const dash = (p / 100) * c
  const color = ringColor(p)
  const gradId = `gf-ring-grad-${size}`
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
    <defs>
      <linearGradient id="${gradId}" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="${color}" stop-opacity=".95"/>
        <stop offset="100%" stop-color="${color}" stop-opacity=".55"/>
      </linearGradient>
    </defs>
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="${stroke}" />
    <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="url(#${gradId})" stroke-width="${stroke}"
      stroke-dasharray="${dash} ${c}" stroke-linecap="round" transform="rotate(-90 ${size / 2} ${size / 2})" />
  </svg>`
}

function teamGaugeSvg(percent: number | null, w: number, h: number): string {
  const p = percent == null ? 0 : Math.min(100, Math.max(0, percent))
  const cx = w / 2
  const cy = h - 4
  const r = Math.min(36, w * 0.4)
  const start = Math.PI
  const end = 0
  const angle = start + (end - start) * (p / 100)
  const nx = cx + r * Math.cos(angle)
  const ny = cy + r * Math.sin(angle)
  const color = ringColor(p)
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
    <path d="M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="5" stroke-linecap="round"/>
    <path d="M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}" fill="none" stroke="${color}" stroke-width="5" stroke-linecap="round"
      stroke-dasharray="${(p / 100) * Math.PI * r} ${Math.PI * r}" />
    <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="#f6f2e8" stroke-width="2" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="3" fill="#f6f2e8"/>
  </svg>`
}

const ICON_REFRESH = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>'
const ICON_THEME = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>'
const ICON_SETTINGS = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
const ICON_CLOSE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>'

const THEME_POP_ID = 'naviforge-gf-theme-pop'

function layoutMetrics(scale: number, heightScale: number) {
  const h = Math.max(0.65, heightScale)
  const ring = Math.round(116 * scale * h)
  const stroke = Math.max(5, Math.round(10 * scale * h))
  const gaugeW = Math.round(88 * scale)
  const gaugeH = Math.round(52 * scale * h)
  const pctFont = Math.round(28 * scale * h)
  return { ring, stroke, gaugeW, gaugeH, pctFont, h }
}

function applyPrefs(root: HTMLElement, prefs: GeniusFallHudPrefs): void {
  const hs = prefs.heightScale ?? 1
  const theme = contrastTheme(prefs.bgColor, prefs.bgOpacity)
  root.style.setProperty('--gf-text', theme.text)
  root.style.setProperty('--gf-muted', theme.muted)
  root.style.setProperty('--gf-line', theme.line)
  root.style.setProperty('--gf-btn', theme.btn)
  root.style.setProperty('--gf-btn-hover', theme.btnHover)
  root.style.setProperty('--gf-badge', theme.badge)
  root.style.setProperty('--gf-badge-text', theme.badgeText)
  root.style.width = `${Math.round(HUD_BASE_WIDTH * prefs.scale)}px`
  root.style.background = bgStyle(prefs)
  root.style.color = theme.text
  root.dataset.gfScale = String(prefs.scale)
  root.dataset.gfHeightScale = String(hs)
  const titleEl = root.querySelector('[data-gf-title-main]')
  if (titleEl) titleEl.textContent = prefs.title
  const inner = root.querySelector('[data-gf-inner]') as HTMLElement | null
  if (inner) inner.style.minHeight = `${Math.round(168 * prefs.scale * hs)}px`
  const body = root.querySelector('[data-gf-body]') as HTMLElement | null
  if (body) body.style.paddingBottom = `${Math.round(8 * hs)}px`
}

function applyState(root: HTMLElement, state: GeniusFallHudState, prefs: GeniusFallHudPrefs): void {
  const hs = prefs.heightScale ?? 1
  const { ring, stroke, gaugeW, gaugeH, pctFont } = layoutMetrics(prefs.scale, hs)
  const loading = Boolean(state.loading)
  const fallen = isQuotaFallen(state)
  root.classList.toggle('gf-fallen', fallen)

  const pct = state.percentUsed
  const ringHost = root.querySelector('[data-gf-ring-main]')
  const teamHost = root.querySelector('[data-gf-team-gauge]')
  const pctEl = root.querySelector('[data-gf-pct]') as HTMLElement | null
  const ringBox = root.querySelector('[data-gf-ring-box]') as HTMLElement | null
  const spendEl = root.querySelector('[data-gf-spend]')
  const teamPctEl = root.querySelector('[data-gf-team-pct]')
  const footEl = root.querySelector('[data-gf-foot]')
  const resetDateEl = root.querySelector('[data-gf-reset-date]')
  const resetSubEl = root.querySelector('[data-gf-reset-sub]')
  const titleSubEl = root.querySelector('[data-gf-title-sub]')
  const errEl = root.querySelector('[data-gf-err]')
  const refreshBtn = root.querySelector('[data-gf-refresh]') as HTMLElement | null

  if (titleSubEl) titleSubEl.textContent = `${state.label} · TEAM USAGE`

  const ringPct =
    fallen
      ? 100
      : pct != null
        ? pct
        : state.spentUsd != null && state.limitUsd != null && state.limitUsd > 0
          ? Math.min(100, (state.spentUsd / state.limitUsd) * 100)
          : null

  if (ringBox) {
    ringBox.style.width = `${ring}px`
    ringBox.style.height = `${ring}px`
  }
  if (ringHost) {
    ringHost.style.width = `${ring}px`
    ringHost.style.height = `${ring}px`
    ringHost.innerHTML = loading
      ? `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;opacity:.5;color:var(--gf-muted)">↻</div>`
      : ringSvg(ringPct, ring, stroke)
  }
  if (teamHost) {
    teamHost.style.width = `${gaugeW}px`
    teamHost.innerHTML = teamGaugeSvg(state.teamPercent, gaugeW, gaugeH)
  }
  if (pctEl) {
    let centerText = '—'
    if (loading) centerText = '…'
    else if (fallen) {
      centerText = '陨落'
      pctEl.style.fontSize = `${Math.max(16, pctFont - 4)}px`
    } else if (state.personalDisplay === 'money' && state.spentUsd != null) {
      centerText = formatUsd(state.spentUsd)
      pctEl.style.fontSize = `${Math.max(14, pctFont - 6)}px`
    } else if (pct != null) {
      centerText = `${Math.round(pct)}%`
      pctEl.style.fontSize = `${pctFont}px`
    } else if (state.spentUsd != null) {
      centerText = formatUsd(state.spentUsd)
      pctEl.style.fontSize = `${Math.max(14, pctFont - 6)}px`
    } else {
      pctEl.style.fontSize = `${pctFont}px`
    }
    pctEl.textContent = centerText
  }
  if (spendEl) {
    const spendText =
      state.spentUsd != null || state.limitUsd != null
        ? `${formatUsd(state.spentUsd)} / ${formatUsd(state.limitUsd)}`
        : state.percentUsed != null
          ? `${Math.round(state.percentUsed)}% used`
          : '—'
    spendEl.textContent = loading ? '拉取额度…' : state.ok ? spendText : state.error ?? '未登录 cursor.com'
  }
  if (teamPctEl) {
    teamPctEl.textContent =
      state.teamPercent != null ? `${Math.round(state.teamPercent)}%` : '—'
  }
  if (resetDateEl) {
    resetDateEl.textContent = state.cycleEnd ? formatReset(state.cycleEnd) : '—'
  }
  if (resetSubEl) {
    const days = daysUntilReset(state.cycleEnd)
    resetSubEl.textContent =
      days != null && state.cycleEnd ? `还剩 ${days} 天重置` : state.cycleEnd ? '本周期结束' : '未获取账单周期'
  }
  if (footEl) {
    if (fallen) {
      const days = daysUntilReset(state.cycleEnd)
      footEl.textContent =
        days != null
          ? `本期额度已耗尽 · ${days} 天后轮回重置 🕯️`
          : '本期额度已耗尽 · 等待账单重置 🕯️'
    } else {
      const parts = [
        state.percentUsed != null ? `已用 ${Math.round(state.percentUsed)}%` : null,
        state.remainingUsd != null ? `剩余 ${formatUsd(state.remainingUsd)}` : null,
        state.spentUsd != null && state.limitUsd != null
          ? `个人 ${formatUsd(state.spentUsd)} / ${formatUsd(state.limitUsd)}`
          : state.spentUsd != null
            ? `本期消费 ${formatUsd(state.spentUsd)}`
            : null,
      ].filter(Boolean)
      footEl.textContent = parts.join(' · ') || (loading ? '同步额度…' : '—')
    }
  }
  if (errEl) {
    const showErr = !state.ok && !loading && state.error
    errEl.textContent = showErr ? state.error ?? '' : ''
    ;(errEl as HTMLElement).style.display = showErr ? 'block' : 'none'
  }
  if (!loading) refreshBtn?.removeAttribute('data-spin')
}

function closeThemePop(): void {
  document.getElementById(THEME_POP_ID)?.remove()
}

function wireThemePicker(
  root: HTMLElement,
  prefs: GeniusFallHudPrefs,
  onPrefsChange: (patch: Partial<GeniusFallHudPrefs>) => void
): void {
  const btn = root.querySelector('[data-gf-theme]') as HTMLButtonElement | null
  if (!btn) return

  btn.addEventListener('click', (e) => {
    e.stopPropagation()
    const existing = document.getElementById(THEME_POP_ID)
    if (existing) {
      existing.remove()
      return
    }
    const rect = btn.getBoundingClientRect()
    const hudRect = root.getBoundingClientRect()
    const pop = document.createElement('div')
    pop.id = THEME_POP_ID
    pop.setAttribute('data-gf-theme-pop', '1')
    const popW = 168
    const left = Math.min(hudRect.right - popW, Math.max(8, hudRect.left))
    const top = Math.max(8, hudRect.top - 132)
    pop.style.cssText = [
      'position:fixed',
      `left:${left}px`,
      `top:${top}px`,
      `width:${popW}px`,
      'padding:10px',
      'border-radius:12px',
      'background:rgba(18,20,19,.98)',
      'border:1px solid rgba(255,255,255,.18)',
      'box-shadow:0 16px 40px rgba(0,0,0,.45)',
      'font:11px/1.35 system-ui,sans-serif',
      'color:#f6f2e8',
      'z-index:2147483647',
    ].join(';')
    pop.innerHTML = `
      <label style="display:block;font-size:9px;opacity:.7;margin-bottom:4px">背景颜色</label>
      <input type="color" data-gf-bg-color value="${prefs.bgColor}" style="width:100%;height:28px;border:0;padding:0;background:transparent;cursor:pointer" />
      <label style="display:block;font-size:9px;opacity:.7;margin:8px 0 4px">透明度 <span data-gf-opacity-label>${Math.round(prefs.bgOpacity * 100)}%</span></label>
      <input type="range" data-gf-bg-opacity min="20" max="100" value="${Math.round(prefs.bgOpacity * 100)}" style="width:100%" />
    `
    document.body.appendChild(pop)

    const colorInput = pop.querySelector('[data-gf-bg-color]') as HTMLInputElement
    const opacityInput = pop.querySelector('[data-gf-bg-opacity]') as HTMLInputElement
    const opacityLabel = pop.querySelector('[data-gf-opacity-label]')

    colorInput?.addEventListener('input', () => {
      const bgColor = colorInput.value
      Object.assign(prefs, { bgColor })
      applyPrefs(root, prefs)
      onPrefsChange({ bgColor })
    })
    opacityInput?.addEventListener('input', () => {
      const bgOpacity = Number(opacityInput.value) / 100
      if (opacityLabel) opacityLabel.textContent = `${opacityInput.value}%`
      Object.assign(prefs, { bgOpacity })
      applyPrefs(root, prefs)
      onPrefsChange({ bgOpacity })
    })

    const onDoc = (ev: PointerEvent) => {
      if ((ev.target as HTMLElement).closest(`#${THEME_POP_ID}, [data-gf-theme]`)) return
      closeThemePop()
      document.removeEventListener('pointerdown', onDoc, true)
    }
    window.setTimeout(() => document.addEventListener('pointerdown', onDoc, true), 0)
  })
}

function makeDraggable(root: HTMLElement, handle: HTMLElement, onMove: (x: number, y: number) => void): void {
  let dragging = false
  let startX = 0
  let startY = 0
  let originX = 0
  let originY = 0

  const onPointerDown = (e: PointerEvent) => {
    if ((e.target as HTMLElement).closest('button, [data-gf-theme-pop], [data-gf-resize]')) return
    dragging = true
    startX = e.clientX
    startY = e.clientY
    const rect = root.getBoundingClientRect()
    originX = rect.left
    originY = rect.top
    handle.setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: PointerEvent) => {
    if (!dragging) return
    const x = Math.max(8, Math.min(window.innerWidth - root.offsetWidth - 8, originX + e.clientX - startX))
    const y = Math.max(8, Math.min(window.innerHeight - root.offsetHeight - 8, originY + e.clientY - startY))
    root.style.left = `${x}px`
    root.style.top = `${y}px`
    root.style.right = 'auto'
    onMove(x, y)
  }
  const onPointerUp = () => {
    dragging = false
  }
  handle.addEventListener('pointerdown', onPointerDown)
  handle.addEventListener('pointermove', onPointerMove)
  handle.addEventListener('pointerup', onPointerUp)
  handle.addEventListener('pointercancel', onPointerUp)
}

function makeResizable(
  root: HTMLElement,
  handle: HTMLElement,
  getPrefs: () => { scale: number; heightScale: number },
  onResize: (patch: { scale?: number; heightScale?: number }) => void
): void {
  let resizing = false
  let startX = 0
  let startY = 0
  let startScale = 1
  let startHeightScale = 1

  const onPointerDown = (e: PointerEvent) => {
    e.stopPropagation()
    resizing = true
    startX = e.clientX
    startY = e.clientY
    const prefs = getPrefs()
    startScale = prefs.scale
    startHeightScale = prefs.heightScale
    handle.setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: PointerEvent) => {
    if (!resizing) return
    const deltaX = e.clientX - startX
    const deltaY = e.clientY - startY
    const scale = Math.min(1.35, Math.max(0.55, startScale + deltaX / 320))
    const heightScale = Math.min(1.35, Math.max(0.65, startHeightScale + deltaY / 280))
    onResize({ scale, heightScale })
  }
  const onPointerUp = () => {
    resizing = false
  }
  handle.addEventListener('pointerdown', onPointerDown)
  handle.addEventListener('pointermove', onPointerMove)
  handle.addEventListener('pointerup', onPointerUp)
  handle.addEventListener('pointercancel', onPointerUp)
}

export function hideGeniusFallHud(): void {
  closeThemePop()
  document.getElementById(ROOT_ID)?.remove()
}

export function isGeniusFallHudVisible(): boolean {
  return Boolean(document.getElementById(ROOT_ID))
}

export function showGeniusFallHud(
  state: GeniusFallHudState,
  prefs: GeniusFallHudPrefs,
  hooks: {
    onMove: (x: number, y: number) => void
    onPrefsChange: (patch: Partial<GeniusFallHudPrefs>) => void
    onRefresh: () => void
    onOpenPanel: () => void
    onClose: () => void
  }
): void {
  hideGeniusFallHud()
  ensureStyles()

  const livePrefs = { ...DEFAULT_HUD_PREFS, ...prefs }

  const root = document.createElement('div')
  root.id = ROOT_ID
  root.setAttribute('data-naviforge-genius-fall-hud', '1')
  root.style.cssText = [
    'position:fixed',
    `left:${livePrefs.x}px`,
    `top:${livePrefs.y}px`,
    'z-index:2147483646',
    `width:${Math.round(HUD_BASE_WIDTH * livePrefs.scale)}px`,
    'border-radius:22px',
    'overflow:visible',
    'font:12px/1.35 "SF Pro Text","Avenir Next",system-ui,sans-serif',
    'color:var(--gf-text,#f6f2e8)',
    'border:1px solid rgba(255,255,255,.16)',
    'box-shadow:0 24px 60px rgba(0,0,0,.42),0 0 0 1px rgba(255,255,255,.04) inset',
    'backdrop-filter:blur(20px) saturate(1.2)',
    '-webkit-backdrop-filter:blur(20px) saturate(1.2)',
    'user-select:none',
  ].join(';')
  applyPrefs(root, livePrefs)

  root.innerHTML = `
    <div data-gf-inner style="position:relative;border-radius:22px;overflow:hidden">
      <div data-gf-drag class="gf-drag" style="display:flex;align-items:flex-start;justify-content:space-between;padding:12px 14px 8px;gap:8px">
        <div style="display:flex;align-items:flex-start;gap:8px;min-width:0">
          <span class="gf-pulse" aria-hidden="true" style="margin-top:4px"></span>
          <div style="min-width:0">
            <div class="gf-title-main" data-gf-title-main>${livePrefs.title}</div>
            <div class="gf-title-sub" data-gf-title-sub>${state.label} · TEAM USAGE</div>
          </div>
        </div>
        <div style="display:flex;gap:5px;flex-shrink:0;align-items:center">
          <button type="button" class="gf-platform-btn" data-gf-platform title="平台开关与设置">平台</button>
          <button type="button" class="gf-btn" data-gf-theme title="背景颜色">${ICON_THEME}</button>
          <button type="button" class="gf-btn" data-gf-refresh title="刷新">${ICON_REFRESH}</button>
          <button type="button" class="gf-btn" data-gf-close title="关闭">${ICON_CLOSE}</button>
        </div>
      </div>
      <div data-gf-body style="position:relative;padding:0 12px 6px">
        <div data-gf-fallen class="gf-fallen-banner" aria-live="polite">
          <div class="gf-fallen-emoji" aria-hidden="true">😭 💀 😭</div>
          <div class="gf-fallen-title">天才已陨落</div>
          <div class="gf-fallen-sub">额度归零，代码之神暂时离线…</div>
        </div>
        <div class="gf-reset-badge">
          <div>
            <div class="gf-reset-label">账单重置日</div>
            <div class="gf-reset-sub" data-gf-reset-sub>—</div>
          </div>
          <div class="gf-reset-date" data-gf-reset-date>—</div>
        </div>
        <div style="display:flex;align-items:flex-end;gap:6px">
          <div data-gf-ring-box style="position:relative;flex-shrink:0">
            <div data-gf-ring-main></div>
            <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;color:var(--gf-text)">
              <div data-gf-pct style="font-weight:700;line-height:1;letter-spacing:-.03em">—</div>
              <div style="font-size:9px;color:var(--gf-muted);margin-top:2px;letter-spacing:.12em">YOU</div>
            </div>
          </div>
          <div style="flex:1;min-width:0;padding-bottom:4px">
            <div data-gf-team-gauge style="margin:0 auto"></div>
            <div style="text-align:center;margin-top:2px;color:var(--gf-text)">
              <div data-gf-team-pct style="font-size:16px;font-weight:650;line-height:1">—</div>
              <div style="font-size:8px;color:var(--gf-muted);letter-spacing:.1em;margin-top:2px">TEAM POOL</div>
            </div>
            <div data-gf-spend style="margin-top:8px;font-size:10px;color:var(--gf-muted);line-height:1.45;text-align:center"></div>
          </div>
        </div>
      </div>
      <div data-gf-err style="display:none;padding:0 14px 6px;font-size:10px;color:#ffb4b4;line-height:1.4"></div>
      <div data-gf-foot style="padding:8px 14px 12px;font-size:10px;color:var(--gf-muted);letter-spacing:.02em;border-top:1px solid var(--gf-line)"></div>
      <div data-gf-resize class="gf-resize" title="拖动缩放"></div>
    </div>
  `

  document.documentElement.appendChild(root)
  applyState(root, state, livePrefs)

  const drag = root.querySelector('[data-gf-drag]') as HTMLElement
  makeDraggable(root, drag, hooks.onMove)

  const resize = root.querySelector('[data-gf-resize]') as HTMLElement
  makeResizable(
    root,
    resize,
    () => ({
      scale: Number(root.dataset.gfScale ?? livePrefs.scale),
      heightScale: Number(root.dataset.gfHeightScale ?? livePrefs.heightScale),
    }),
    (patch) => {
      if (patch.scale != null) livePrefs.scale = patch.scale
      if (patch.heightScale != null) livePrefs.heightScale = patch.heightScale
      applyPrefs(root, livePrefs)
      applyState(root, state, livePrefs)
      hooks.onPrefsChange(patch)
    }
  )

  wireThemePicker(root, livePrefs, (patch) => {
    Object.assign(livePrefs, patch)
    hooks.onPrefsChange(patch)
    if (patch.bgColor != null || patch.bgOpacity != null) applyState(root, state, livePrefs)
  })

  root.querySelector('[data-gf-refresh]')?.addEventListener('click', (e) => {
    ;(e.currentTarget as HTMLElement).setAttribute('data-spin', '1')
    hooks.onRefresh()
  })
  root.querySelector('[data-gf-platform]')?.addEventListener('click', hooks.onOpenPanel)
  root.querySelector('[data-gf-close]')?.addEventListener('click', hooks.onClose)
}

export function updateGeniusFallHud(
  state: GeniusFallHudState,
  prefs?: GeniusFallHudPrefs
): void {
  const root = document.getElementById(ROOT_ID)
  if (!root) return
  const scale = Number(root.dataset.gfScale ?? DEFAULT_HUD_PREFS.scale)
  const heightScale = Number(root.dataset.gfHeightScale ?? DEFAULT_HUD_PREFS.heightScale)
  const livePrefs = prefs ?? { ...DEFAULT_HUD_PREFS, scale, heightScale }
  applyState(root, state, livePrefs)
}

export function toggleGeniusFallHud(
  state: GeniusFallHudState,
  prefs: GeniusFallHudPrefs,
  hooks: Parameters<typeof showGeniusFallHud>[2]
): boolean {
  if (isGeniusFallHudVisible()) {
    hideGeniusFallHud()
    return false
  }
  showGeniusFallHud(state, prefs, hooks)
  return true
}
