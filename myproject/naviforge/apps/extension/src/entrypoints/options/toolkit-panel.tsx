import { useEffect, useState } from 'react'
import type { DomContentItem } from '@naviforge/dom-plane'

import { useI18n } from '../../i18n'
import {
  bindToolkitToRecentWebTab,
  buildExtractJsonl,
  downloadTextFile,
  isToolkitPageUrl,
  listToolkitTabs,
  resolveToolkitTab,
  switchToolkitTab,
  type ToolkitTabRef,
  toolkitExtract,
  toolkitFullPageScreenshot,
  toolkitMarkTopn,
  toolkitOpenTranslate,
  toolkitScreenshot,
} from '../../lib/toolkit-actions'
import {
  formatPublicIp,
  formatTraceroute,
  lookupPublicIp,
  runHostTraceroute,
} from '../../lib/net-diag'
import { formatTranslationFeedback, TRANSLATE_LANGS, isTranslateLangId } from '../../lib/page-translate'
import { STORAGE } from '../../lib/settings'
import { loadToolkitCapabilityGates, toolkitGateBlocked } from '../../lib/toolkit-gates'
import type { AgentCapabilityGates } from '@naviforge/shared'
import { runToolkitOcr } from '../../lib/vision-ocr'
import { toolkitToggleVideoSubtitles } from '../../lib/video-subtitles'
import { SCREENSHOT_STUDIO_MESSAGE } from '../../modules/screenshot-studio'
import { ModifyHeadersPanel } from './modify-headers-panel'
import { JsonFormatDrawer } from './json-format-drawer'
import { RunResultDrawer, type ToolkitRunResult } from './run-result-drawer'

async function persistToolkitShot(dataUrl: string, kind: string): Promise<string> {
  const { downloadFallback, saveWorkspaceShot } = await import('../../lib/local-workspace')
  const saved = await saveWorkspaceShot({ kind, dataUrl, tool: `toolkit.${kind}` })
  if (saved?.relativePath) return saved.relativePath
  const filename = `shots/naviforge-${kind}-${Date.now()}.png`
  await downloadFallback(dataUrl, filename, true)
  return `Downloads/NaviForge/${filename}`
}

function PageTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <header className="page-title">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </header>
  )
}

const TOOL_ITEMS = [
  { id: 'studio', shortcut: '⌘⇧S' },
  { id: 'screenshot', shortcut: '⌥A' },
  { id: 'fullpage', shortcut: '⌥S' },
  { id: 'extract', shortcut: '—', usesTopN: true },
  { id: 'mark', shortcut: '—', usesTopN: true },
  { id: 'translate', shortcut: '⌥T' },
  { id: 'subs', shortcut: '—' },
  { id: 'ocr', shortcut: '—' },
  { id: 'json', shortcut: '—', noTab: true },
  { id: 'myip', shortcut: '—', noTab: true },
] as const

type ToolId = (typeof TOOL_ITEMS)[number]['id']

export function ToolkitPanel() {
  const { t } = useI18n()
  const [tab, setTab] = useState<chrome.tabs.Tab | null>(null)
  const [allTabs, setAllTabs] = useState<ToolkitTabRef[]>([])
  const [tabPickerOpen, setTabPickerOpen] = useState(false)
  const [topN, setTopN] = useState(10)
  const [busy, setBusy] = useState<ToolId | null>(null)
  const [notice, setNotice] = useState('')
  const [noticeOk, setNoticeOk] = useState(true)
  const [items, setItems] = useState<DomContentItem[]>([])
  const [ipQuery, setIpQuery] = useState('')
  const [translateLang, setTranslateLang] = useState('zh-CN')
  const [tracerouteBusy, setTracerouteBusy] = useState(false)
  const [jsonOpen, setJsonOpen] = useState(false)
  const [result, setResult] = useState<ToolkitRunResult | null>(null)
  const [gates, setGates] = useState<AgentCapabilityGates | null>(null)

  async function refreshTab(): Promise<chrome.tabs.Tab | null> {
    const next = await resolveToolkitTab()
    setTab(next)
    return next
  }

  const tabReady = Boolean(tab?.id && isToolkitPageUrl(tab.url))

  async function focusBoundTab(): Promise<void> {
    if (!tab?.id) return
    await chrome.tabs.update(tab.id, { active: true })
    if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true })
  }

  useEffect(() => {
    void loadToolkitCapabilityGates().then(setGates)
    void (async () => {
      let next = await refreshTab()
      if (!next?.id || !isToolkitPageUrl(next.url)) {
        next = await bindToolkitToRecentWebTab()
        setTab(next)
      }
      if (!next?.id) void openTabPicker()
      const stored = await chrome.storage.local.get([
        STORAGE.openJsonDrawer,
        STORAGE.openToolkitRunResult,
        STORAGE.translateTargetLang,
      ])
      if (stored[STORAGE.openJsonDrawer]) {
        setResult(null)
        setJsonOpen(true)
        await chrome.storage.local.remove(STORAGE.openJsonDrawer)
      }
      const pendingResult = stored[STORAGE.openToolkitRunResult]
      if (pendingResult && typeof pendingResult === 'object') {
        setResult(pendingResult as ToolkitRunResult)
        setJsonOpen(false)
        await chrome.storage.local.remove(STORAGE.openToolkitRunResult)
      }
      const lang = stored[STORAGE.translateTargetLang]
      if (typeof lang === 'string' && isTranslateLangId(lang)) setTranslateLang(lang)
    })()
    const onUpdated = (tabId: number, change: chrome.tabs.TabChangeInfo): void => {
      if (!change.url && !change.title) return
      setTab((current) => (current?.id === tabId ? { ...current, ...change } : current))
    }
    const onRemoved = (tabId: number): void => {
      setTab((current) => (current?.id === tabId ? null : current))
    }
    const onStorage = (
      changes: { [key: string]: chrome.storage.StorageChange },
      area: string
    ): void => {
      if (area !== 'local') return
      if (changes[STORAGE.privacy]) void loadToolkitCapabilityGates().then(setGates)
      if (changes[STORAGE.openJsonDrawer]?.newValue) {
        setResult(null)
        setJsonOpen(true)
        void chrome.storage.local.remove(STORAGE.openJsonDrawer)
      }
      if (changes[STORAGE.openToolkitRunResult]?.newValue) {
        setResult(changes[STORAGE.openToolkitRunResult].newValue as ToolkitRunResult)
        setJsonOpen(false)
        void chrome.storage.local.remove(STORAGE.openToolkitRunResult)
      }
    }
    chrome.tabs.onUpdated.addListener(onUpdated)
    chrome.tabs.onRemoved.addListener(onRemoved)
    chrome.storage.onChanged.addListener(onStorage)
    return () => {
      chrome.tabs.onUpdated.removeListener(onUpdated)
      chrome.tabs.onRemoved.removeListener(onRemoved)
      chrome.storage.onChanged.removeListener(onStorage)
    }
  }, [])

  useEffect(() => {
    if (!tabPickerOpen) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setTabPickerOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [tabPickerOpen])

  function flash(message: string, ok = true): void {
    setNoticeOk(ok)
    setNotice(message)
    window.setTimeout(() => setNotice(''), 5000)
  }

  async function requireTab(): Promise<chrome.tabs.Tab | null> {
    const current = tab ?? (await refreshTab())
    if (!current?.id) {
      flash(t('options.notice.toolkitNeedPage'), false)
      return null
    }
    if (!isToolkitPageUrl(current.url)) {
      flash(t('options.notice.toolkitRestrictedPage'), false)
      return null
    }
    return current
  }

  async function openTabPicker(): Promise<void> {
    const tabs = await listToolkitTabs()
    setAllTabs(tabs)
    setTabPickerOpen(true)
    if (!tabs.length) flash(t('options.notice.toolkitNoTabs'), false)
  }

  function showResult(next: ToolkitRunResult): void {
    setJsonOpen(false)
    setResult(next)
  }

  async function runTool(id: ToolId): Promise<void> {
    if (id === 'json') {
      setResult(null)
      setJsonOpen(true)
      return
    }
    const started = Date.now()
    if (id === 'myip') {
      const blocked = gates ? toolkitGateBlocked(gates, 'networkEnabled') : null
      if (blocked) {
        flash(blocked, false)
        return
      }
      setBusy(id)
      try {
        const info = await lookupPublicIp(ipQuery)
        setItems([])
        showResult({
          kind: 'ip',
          title: t('options.toolkit.tools.myip.title'),
          target: info.ip,
          elapsedMs: Date.now() - started,
          text: formatPublicIp(info),
          latitude: info.latitude,
          longitude: info.longitude,
        })
        flash(
          ipQuery.trim()
            ? t('options.notice.toolkitIpQueried', { ip: info.ip })
            : t('options.notice.toolkitIpEgress', { ip: info.ip })
        )
      } catch (error) {
        flash((error as Error).message, false)
      } finally {
        setBusy(null)
      }
      return
    }
    const current = await requireTab()
    if (!current?.id) return
    setBusy(id)
    const restoreId =
      id === 'studio' || id === 'screenshot' || id === 'fullpage'
        ? (await chrome.tabs.getCurrent())?.id
        : undefined
    try {
      const target = current.title || current.url
      if (id === 'studio') {
        const launched = (await chrome.runtime.sendMessage({
          type: SCREENSHOT_STUDIO_MESSAGE.launch,
          tabId: current.id,
        })) as { ok?: boolean; cancelled?: boolean; error?: string }
        if (launched?.cancelled) {
          flash(t('options.notice.toolkitCancelled'))
          return
        }
        if (launched && launched.ok === false && launched.error) throw new Error(launched.error)
        return
      }
      if (id === 'screenshot') {
        const shot = await toolkitScreenshot(current.id)
        if (!shot.ok) throw new Error(shot.error.message)
        if (!shot.data?.dataUrl) throw new Error('screenshot failed')
        const path = await persistToolkitShot(shot.data.dataUrl, 'visible')
        showResult({
          kind: 'screenshot',
          title: t('options.toolkit.runTitles.visibleScreenshot'),
          target,
          elapsedMs: Date.now() - started,
          dataUrl: shot.data.dataUrl,
        })
        flash(t('options.notice.toolkitSaved', { path }))
        return
      }
      if (id === 'fullpage') {
        const shot = await toolkitFullPageScreenshot(current.id)
        if (!shot.ok) throw new Error(shot.error.message)
        if (!shot.data?.dataUrl) throw new Error('fullpage screenshot failed')
        const path = await persistToolkitShot(shot.data.dataUrl, 'fullpage')
        showResult({
          kind: 'screenshot',
          title: t('options.toolkit.runTitles.fullpageScreenshot'),
          target,
          elapsedMs: Date.now() - started,
          dataUrl: shot.data.dataUrl,
          meta: `${shot.data.width}×${shot.data.height} · ${shot.data.slices} slices`,
        })
        flash(t('options.notice.toolkitSaved', { path }))
        return
      }
      if (id === 'extract') {
        const extracted = await toolkitExtract(current.id, topN)
        if (!extracted.ok) throw new Error(extracted.error.message)
        setItems(extracted.data.items)
        const meta = [
          extracted.data.strategy &&
            t('options.toolkit.runMeta.strategy', { value: extracted.data.strategy }),
          extracted.data.profileId &&
            t('options.toolkit.runMeta.profile', { value: extracted.data.profileId }),
          extracted.data.shortfall,
        ]
          .filter(Boolean)
          .join(' · ')
        showResult({
          kind: 'list',
          title: t('options.toolkit.runTitles.extract', { count: extracted.data.items.length }),
          target,
          elapsedMs: Date.now() - started,
          items: extracted.data.items,
          meta,
        })
        flash(
          extracted.data.shortfall
            ? t('options.notice.toolkitExtractShortfall', {
                count: extracted.data.items.length,
                topN,
              })
            : t('options.notice.toolkitExtracted', { count: extracted.data.items.length }),
          !extracted.data.shortfall
        )
        return
      }
      if (id === 'mark') {
        const marked = await toolkitMarkTopn(current.id, topN)
        if (!marked.ok) throw new Error(marked.error.message)
        setItems(marked.data.items)
        showResult({
          kind: 'list',
          title: t('options.toolkit.runTitles.marked', { count: marked.data.marked }),
          target,
          elapsedMs: Date.now() - started,
          items: marked.data.items,
          meta: t('options.toolkit.runMeta.markedOnPage', { count: marked.data.marked }),
        })
        flash(t('options.notice.toolkitMarked', { count: marked.data.marked }))
        return
      }
      if (id === 'translate') {
        const opened = await toolkitOpenTranslate(current, translateLang)
        if (!opened.ok) throw new Error(opened.error ?? 'translate failed')
        const text = formatTranslationFeedback(opened)
        showResult({
          kind: 'note',
          title: t('options.toolkit.runTitles.translate'),
          target,
          elapsedMs: Date.now() - started,
          text,
        })
        flash(text)
        return
      }
      if (id === 'subs') {
        const subs = await toolkitToggleVideoSubtitles(current)
        if (!subs.ok) throw new Error(subs.error ?? 'subtitles failed')
        showResult({
          kind: 'note',
          title: t('options.toolkit.runTitles.subs'),
          target,
          elapsedMs: Date.now() - started,
          text: subs.message ?? (subs.active ? t('options.toolkit.subsOn') : t('options.toolkit.subsOff')),
        })
        flash(subs.message ?? t('options.toolkit.subsUpdated'))
        return
      }
      if (id === 'ocr') {
        const ocr = await runToolkitOcr(current)
        if ('cancelled' in ocr) {
          flash(t('options.notice.toolkitCancelled'))
          return
        }
        showResult({
          kind: 'note',
          title: t('options.toolkit.runTitles.ocr'),
          target,
          elapsedMs: Date.now() - started,
          text: ocr.text,
        })
        flash(ocr.path ? t('options.notice.toolkitSaved', { path: ocr.path }) : t('options.notice.toolkitOcrDone'))
      }
    } catch (error) {
      flash((error as Error).message, false)
    } finally {
      if (restoreId != null) await chrome.tabs.update(restoreId, { active: true }).catch(() => {})
      setBusy(null)
    }
  }

  function exportJsonl(): void {
    if (!items.length) {
      flash(t('options.notice.toolkitNeedListFirst'), false)
      return
    }
    downloadTextFile(buildExtractJsonl(items), `naviforge-extract-${Date.now()}.jsonl`)
    flash(t('options.notice.toolkitExportedJsonl', { count: items.length }))
  }

  const tabLabel = tab?.title || tab?.url || t('options.toolkit.notSelected')

  return (
    <>
      <PageTitle
        eyebrow={t('options.toolkit.eyebrow')}
        title={t('options.toolkit.title')}
        description={t('options.toolkit.description')}
      />

      {notice ? (
        <div className={noticeOk ? 'notice' : 'notice bad'} role="status">
          {notice}
        </div>
      ) : null}

      <section className="toolkit-wizard">
        <article className={`toolkit-step ${tabReady ? 'toolkit-step-done' : 'toolkit-step-active'}`}>
          <span className="toolkit-step-badge">1</span>
          <div className="toolkit-step-body">
            <h2>{t('options.toolkit.step1Title')}</h2>
            <p className="toolkit-step-lead">{t('options.toolkit.step1Lead')}</p>
            {tabReady ? (
              <div className="toolkit-bound-card">
                <span className="toolkit-bound-label">{t('options.toolkit.step1Selected')}</span>
                <strong>{tabLabel}</strong>
                {tab?.url ? <small>{tab.url}</small> : null}
                <div className="toolkit-bound-actions">
                  <button type="button" className="button secondary" onClick={() => void focusBoundTab()}>
                    {t('options.common.buttons.switchTab')}
                  </button>
                  <button type="button" className="button ghost" onClick={() => void openTabPicker()}>
                    {t('options.common.buttons.pickAnother')}
                  </button>
                </div>
              </div>
            ) : (
              <ol className="toolkit-steps-list">
                <li>{t('options.toolkit.step1Instructions.0')}</li>
                <li>{t('options.toolkit.step1Instructions.1')}</li>
                <li>{t('options.toolkit.step1Instructions.2')}</li>
              </ol>
            )}
            {!tabReady ? (
              <div className="toolkit-target-actions">
                <button
                  type="button"
                  className="button primary"
                  onClick={() =>
                    void bindToolkitToRecentWebTab().then((next) => {
                      setTab(next)
                      if (next) flash(t('options.notice.toolkitSelected', { label: next.title || next.url || '' }))
                      else void openTabPicker()
                    })
                  }
                >
                  {t('options.common.buttons.pickRecent')}
                </button>
                <button type="button" className="button secondary" onClick={() => void openTabPicker()}>
                  {t('options.common.buttons.pickPage')}
                </button>
              </div>
            ) : null}
          </div>
        </article>

        <article
          className={`toolkit-step ${tabReady ? 'toolkit-step-active' : 'toolkit-step-locked'}`}
        >
          <span className="toolkit-step-badge">2</span>
          <div className="toolkit-step-body">
            <h2>{t('options.toolkit.step2Title')}</h2>
            {!tabReady ? (
              <p className="toolkit-step-warn">{t('options.toolkit.step2Locked')}</p>
            ) : (
              <p className="toolkit-step-lead">{t('options.toolkit.step2Lead')}</p>
            )}
            <div className="data-list toolkit-step-tools">
              <div className="data-list-head data-list-toolkit">
                <span>{t('options.toolkit.table.tool')}</span>
                <span>{t('options.toolkit.table.hint')}</span>
                <span>{t('options.toolkit.table.shortcut')}</span>
                <span>{t('options.toolkit.table.action')}</span>
              </div>
              {TOOL_ITEMS.map((tool) => (
                <article className="data-list-row data-list-toolkit" key={tool.id}>
                  <div className="data-list-main">
                    <strong>{t(`options.toolkit.tools.${tool.id}.label`)}</strong>
                    {'usesTopN' in tool && tool.usesTopN ? (
                      <label className="toolkit-topn inline">
                        <span>{t('options.common.labels.top')}</span>
                        <input
                          type="number"
                          min={1}
                          max={50}
                          value={topN}
                          onChange={(event) =>
                            setTopN(Math.max(1, Math.min(50, Number(event.target.value) || 10)))
                          }
                        />
                      </label>
                    ) : null}
                    {tool.id === 'translate' ? (
                      <label className="toolkit-topn inline">
                        <span>{t('options.common.labels.translateTo')}</span>
                        <select
                          value={translateLang}
                          onChange={(event) => {
                            const next = event.target.value
                            setTranslateLang(next)
                            void chrome.storage.local.set({ [STORAGE.translateTargetLang]: next })
                          }}
                        >
                          {TRANSLATE_LANGS.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    {tool.id === 'myip' ? (
                      <label className="toolkit-topn inline">
                        <span>{t('options.common.labels.ip')}</span>
                        <input
                          type="text"
                          value={ipQuery}
                          placeholder={t('options.toolkit.tools.myip.placeholder')}
                          onChange={(event) => setIpQuery(event.target.value)}
                          style={{ width: '11rem' }}
                        />
                      </label>
                    ) : null}
                  </div>
                  <span className="data-list-meta">{t(`options.toolkit.tools.${tool.id}.hint`)}</span>
                  <span className="data-list-badge">{tool.shortcut}</span>
                  <div className="data-list-actions">
                    <button
                      className="button primary"
                      disabled={
                        busy !== null || (!('noTab' in tool && tool.noTab) && !tabReady)
                      }
                      title={
                        tool.id === 'myip'
                          ? t('options.toolkit.tooltips.myip')
                          : tool.id === 'json'
                            ? t('options.toolkit.tooltips.json')
                            : tabReady
                              ? t('options.toolkit.tooltips.runOnTab', { label: tabLabel })
                              : t('options.toolkit.tooltips.completeStep1')
                      }
                      onClick={() => void runTool(tool.id)}
                    >
                      {busy === tool.id
                        ? t('options.common.buttons.processing')
                        : t('options.common.buttons.running')}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </article>

        <article className="toolkit-step toolkit-step-muted">
          <span className="toolkit-step-badge">3</span>
          <div className="toolkit-step-body">
            <h2>{t('options.toolkit.step3Title')}</h2>
            <p className="toolkit-step-lead">{t('options.toolkit.step3Lead')}</p>
          </div>
        </article>
      </section>

      <details className="toolkit-shortcut-box">
        <summary>{t('options.toolkit.shortcutsSummary')}</summary>
        <p>{t('options.toolkit.shortcutsBody')}</p>
      </details>

      {tabPickerOpen ? (
        <div className="toolkit-tab-picker">
          <strong>{t('options.toolkit.tabPickerTitle')}</strong>
          {!allTabs.length ? (
            <p className="session-hint">{t('options.toolkit.tabPickerEmpty')}</p>
          ) : (
            allTabs.map((entry) => (
              <button
                key={entry.id}
                type="button"
                className={tab?.id === entry.id ? 'toolkit-tab-option active' : 'toolkit-tab-option'}
                onClick={() => {
                  void switchToolkitTab(entry.id, entry.windowId).then((next) => {
                    setTab(next)
                    setTabPickerOpen(false)
                    flash(
                      next
                        ? t('options.notice.toolkitSwitched', { id: next.id ?? 0 })
                        : t('options.notice.toolkitSwitchFailed'),
                      Boolean(next)
                    )
                  })
                }}
              >
                #{entry.id} · {entry.title || entry.url}
                {entry.active ? ` · ${t('options.common.status.currentActive')}` : ''}
              </button>
            ))
          )}
          <button type="button" className="text-button" onClick={() => setTabPickerOpen(false)}>
            {t('options.toolkit.tabPickerClose')}
          </button>
        </div>
      ) : null}

      <ModifyHeadersPanel />

      <RunResultDrawer
        result={result}
        onClose={() => setResult(null)}
        onCopy={(text) => {
          void navigator.clipboard
            .writeText(text)
            .then(() => flash(t('options.notice.toolkitCopied')))
            .catch(() => flash(t('options.notice.copyFailed', { message: 'clipboard' }), false))
        }}
        onExportList={exportJsonl}
        onSaveImage={(dataUrl) => {
          void persistToolkitShot(dataUrl, 'shot').then((path) =>
            flash(t('options.notice.toolkitSaved', { path }))
          )
        }}
        onDownloadText={(text) => {
          downloadTextFile(text, `naviforge-ocr-${Date.now()}.txt`)
          flash(t('options.notice.toolkitDownloaded'))
        }}
        tracerouteBusy={tracerouteBusy}
        onTraceroute={() => {
          const target = result?.kind === 'ip' ? result.target : undefined
          if (!target) return
          setTracerouteBusy(true)
          void runHostTraceroute(target)
            .then((trace) => {
              const text = formatTraceroute(trace)
              setResult((current) =>
                current?.kind === 'ip' ? { ...current, traceroute: text } : current
              )
              flash(t('options.notice.toolkitTracerouteDone'))
            })
            .catch((error) => flash((error as Error).message, false))
            .finally(() => setTracerouteBusy(false))
        }}
      />
      <JsonFormatDrawer open={jsonOpen} onClose={() => setJsonOpen(false)} />
    </>
  )
}
