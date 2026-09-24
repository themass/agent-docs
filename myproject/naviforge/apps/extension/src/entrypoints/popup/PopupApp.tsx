import { useCallback, useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Braces,
  Camera,
  Circle,
  Crop,
  Film,
  Gauge,
  Globe,
  Grid3x3,
  Languages,
  LayoutPanelLeft,
  List,
  LogIn,
  Maximize2,
  ScanText,
  ScrollText,
  Settings,
  Subtitles,
  Target,
  Wrench,
} from 'lucide-react'

import { AuthStatusBar } from '../../components/auth-status-bar'
import { BrandMark } from '../../components/brand-mark'
import { useI18n } from '../../i18n'
import {
  getBehaviorRecordingStatus,
  openBehaviorRecordingHud,
} from '../../lib/behavior-recording-actions'
import { isNewApiLoggedIn, loadNewApiAuth } from '../../lib/newapi-auth'
import { syncManagedProfilesFromNewApi } from '../../lib/newapi-sync'
import {
  POPUP_WAIT_KEYS,
  TOOLKIT_CATALOG,
  popupI18nKey,
  type ToolkitCatalogId,
  type ToolkitCatalogItem,
} from '../../lib/toolkit-catalog'
import { runPopupTool } from '../../lib/toolkit-popup-actions'
import { snapshotCurrentWebTab } from '../../lib/toolkit-actions'
import { openOptionsPageFromPopup } from '../../lib/surface-launch'

const TOOL_ICONS: Record<ToolkitCatalogId, LucideIcon> = {
  'page-toollist': Grid3x3,
  workspace: Maximize2,
  sidepanel: LayoutPanelLeft,
  studio: Crop,
  screenshot: Camera,
  fullpage: ScrollText,
  extract: List,
  mark: Target,
  translate: Languages,
  subs: Subtitles,
  'genius-fall': Gauge,
  'behavior-forge': Film,
  ocr: ScanText,
  json: Braces,
  myip: Globe,
  'toolkit-admin': Wrench,
  settings: Settings,
  account: LogIn,
}

const POPUP_FOOTER_TOOLS = new Set<ToolkitCatalogId>([
  'account',
  'toolkit-admin',
  'workspace',
  'settings',
  'behavior-forge',
])

const SECTION_ORDER: ToolkitCatalogItem['section'][] = ['quick', 'capture', 'page', 'utility']

const POPUP_FOOTER_ROW: ToolkitCatalogId[] = ['toolkit-admin', 'workspace']

const SECTION_I18N: Record<ToolkitCatalogItem['section'], string> = {
  quick: 'sectionQuick',
  capture: 'sectionCapture',
  page: 'sectionPage',
  utility: 'sectionUtility',
  nav: 'sectionNav',
}

const KEEP_OPEN_TOOLS = new Set<ToolkitCatalogId>(['behavior-forge'])

function pageHost(url: string | undefined): string {
  if (!url) return ''
  try {
    return new URL(url).hostname
  } catch {
    return ''
  }
}

export function PopupApp() {
  const { t } = useI18n()
  const [busy, setBusy] = useState('')
  const [host, setHost] = useState('')
  const [recording, setRecording] = useState(false)
  const [eventCount, setEventCount] = useState(0)

  const refreshRecording = useCallback(async () => {
    const status = await getBehaviorRecordingStatus()
    setRecording(status.recording)
    setEventCount(status.eventCount)
  }, [])

  useEffect(() => {
    void snapshotCurrentWebTab().then((tab) => setHost(pageHost(tab?.url)))
    void refreshRecording()
    void (async () => {
      const auth = await loadNewApiAuth()
      if (isNewApiLoggedIn(auth)) {
        await syncManagedProfilesFromNewApi().catch(() => {})
      }
    })()
  }, [refreshRecording])

  useEffect(() => {
    if (!recording) return
    const id = window.setInterval(() => {
      void getBehaviorRecordingStatus().then((s) => setEventCount(s.eventCount))
    }, 1000)
    return () => window.clearInterval(id)
  }, [recording])

  const [footerBefore, footerAfter] = t('popup.footerHost').split('{host}')

  async function openRecordingConsole(): Promise<void> {
    setBusy(t('popup.behaviorWorking'))
    try {
      const result = await openBehaviorRecordingHud()
      if (!result.ok) {
        throw new Error(
          result.error === 'need_tab' ? t('popup.needWebTab') : result.error ?? 'failed'
        )
      }
      window.close()
    } catch (error) {
      setBusy('')
      window.alert((error as Error).message)
    }
  }

  function runTool(id: ToolkitCatalogId, waitHint?: string) {
    if (waitHint) setBusy(waitHint)
    void runPopupTool(id)
      .then(async (result) => {
        if (!result.ok && result.error) throw new Error(result.error)
        if (id === 'behavior-forge') await refreshRecording()
        if (!KEEP_OPEN_TOOLS.has(id)) window.close()
        else setBusy('')
      })
      .catch((error) => {
        setBusy('')
        window.alert((error as Error).message)
      })
  }

  function renderToolButton(id: ToolkitCatalogId) {
    const item = TOOLKIT_CATALOG.find((entry) => entry.id === id)
    const Icon = TOOL_ICONS[id]
    const i18nKey = popupI18nKey(id)
    const waitKey = POPUP_WAIT_KEYS[id]
    const waitHint = waitKey ? t(`popup.${waitKey}` as 'popup.studioWait') : ''
    const primary = id === 'sidepanel'
    const featured = id === 'page-toollist' || id === 'genius-fall'
    const shortcut = item?.shortcut
    const hint =
      id === 'behavior-forge' && recording
        ? t('popup.behaviorForgeStopHint', { count: eventCount })
        : t(`popup.${i18nKey}Hint` as 'popup.workspaceHint')
    const label =
      id === 'behavior-forge' && recording
        ? t('popup.behaviorForgeStop', { count: eventCount })
        : t(`popup.${i18nKey}` as 'popup.workspace')

    return (
      <button
        key={id}
        type="button"
        disabled={Boolean(busy)}
        title={hint}
        className={
          id === 'behavior-forge' && recording
            ? 'nf-popup-btn nf-popup-btn-dense border border-[#f0a8a8] bg-[#fff5f5]'
            : primary
              ? 'nf-popup-btn nf-popup-btn-dense nf-popup-btn-primary'
              : featured
                ? 'nf-popup-btn nf-popup-btn-dense border border-[#c8e4a8] bg-[#eef8e3]'
                : 'nf-popup-btn nf-popup-btn-dense'
        }
        onClick={() => runTool(id, waitHint)}
      >
        <Icon className="size-3.5 shrink-0" />
        <span className="min-w-0 flex-1 overflow-hidden text-left">
          <span className="block truncate text-[11px] font-semibold leading-tight">{label}</span>
          <span className="block truncate text-[9px] leading-tight text-[var(--nf-muted)]">{hint}</span>
        </span>
        {shortcut ? (
          <span className="shrink-0 text-[9px] font-medium tabular-nums text-[var(--nf-muted)]">{shortcut}</span>
        ) : null}
      </button>
    )
  }

  function renderFooterToolButton(id: ToolkitCatalogId) {
    const Icon = TOOL_ICONS[id]
    const i18nKey = popupI18nKey(id)
    const label =
      id === 'toolkit-admin'
        ? t('popup.openToolkitAdmin')
        : t(`popup.${i18nKey}` as 'popup.workspace')
    const hint =
      id === 'toolkit-admin'
        ? t('popup.openToolkitAdminHint')
        : t(`popup.${i18nKey}Hint` as 'popup.workspaceHint')

    return (
      <button
        key={id}
        type="button"
        disabled={Boolean(busy)}
        className="nf-popup-footer-btn min-w-0 border border-[var(--nf-line)] bg-[#f4f7f5]"
        title={hint}
        onClick={() => runTool(id)}
      >
        <Icon className="size-3 shrink-0" />
        <span className="min-w-0 flex-1 overflow-hidden text-[10px] font-semibold leading-tight whitespace-nowrap truncate">
          {label}
        </span>
      </button>
    )
  }

  return (
    <div className="nf-popup flex h-full min-h-0 w-full flex-col overflow-hidden bg-[var(--nf-paper)] text-[var(--nf-ink)]">
      <header className="shrink-0 border-b border-[var(--nf-line)] px-3 py-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <BrandMark size={26} />
              <p className="text-[10px] font-semibold leading-snug">{t('popup.title')}</p>
            </div>
            <p className="mt-1 text-[9px] leading-snug text-[var(--nf-muted)]">{t('popup.shortcuts')}</p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <AuthStatusBar variant="popup" chip />
            <button
              type="button"
              className="nf-popup-settings-btn"
              title={t('popup.settingsHint')}
              onClick={() => {
                openOptionsPageFromPopup('settings')
                window.close()
              }}
            >
              <Settings className="size-4" />
            </button>
          </div>
        </div>
      </header>

      {recording ? (
        <div className="flex items-center gap-2 border-b border-[#f0d4d4] bg-[#fff6f6] px-3 py-1.5 text-[10px] text-[#a33]">
          <Circle className="size-2 fill-current animate-pulse" />
          <span>{t('popup.behaviorRecording', { count: eventCount })}</span>
        </div>
      ) : null}

      <div className="nf-popup-scroll min-h-0 flex-1 overflow-y-auto px-2.5 py-1.5">
        {SECTION_ORDER.map((section) => {
          const items = TOOLKIT_CATALOG.filter(
            (entry) => entry.section === section && !POPUP_FOOTER_TOOLS.has(entry.id)
          )
          if (!items.length) return null
          return (
            <section key={section} className="mb-2 last:mb-0.5">
              <p className="nf-popup-section">{t(`popup.${SECTION_I18N[section]}` as 'popup.sectionQuick')}</p>
              <div className="grid gap-1">{items.map((entry) => renderToolButton(entry.id))}</div>
            </section>
          )
        })}
      </div>

      <footer className="nf-popup-footer shrink-0 border-t border-[var(--nf-line)] bg-[#f3f0e6] px-3 pt-2 pb-2.5">
        <button
          type="button"
          disabled={Boolean(busy)}
          className="nf-popup-record-btn mb-1.5 w-full"
          title={t('popup.behaviorOpenConsoleHint')}
          onClick={() => void openRecordingConsole()}
        >
          <Film className="size-3.5 shrink-0 text-[#c44]" />
          <div className="min-w-0 flex-1 text-left">
            <div className="text-[11px] font-semibold leading-tight">
              {recording
                ? t('popup.behaviorRecording', { count: eventCount })
                : t('popup.behaviorOpenConsole')}
            </div>
            <div className="mt-0.5 text-[9px] leading-snug text-[var(--nf-muted)]">
              {recording ? t('popup.behaviorForgeStopHint', { count: eventCount }) : t('popup.behaviorReplayHint')}
            </div>
          </div>
        </button>

        <div className="mb-1 grid grid-cols-2 gap-1">
          {POPUP_FOOTER_ROW.map((id) => renderFooterToolButton(id))}
        </div>

        {host ? (
          <p className="truncate pb-0.5 text-[9px] leading-snug text-[var(--nf-muted)]" title={host}>
            {busy ||
              (footerAfter !== undefined ? (
                <>
                  {footerBefore}
                  <strong>{host}</strong>
                  {footerAfter}
                </>
              ) : (
                t('popup.footerHost', { host })
              ))}
          </p>
        ) : (
          <p className="pb-0.5 text-[9px] leading-snug text-[var(--nf-muted)]">
            {busy || t('popup.footerEmpty')}
          </p>
        )}
      </footer>
    </div>
  )
}
