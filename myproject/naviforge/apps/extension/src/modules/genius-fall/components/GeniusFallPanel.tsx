import { useCallback, useEffect, useMemo, useState } from 'react'

import { useI18n } from '../../../i18n'
import { listQuotaProviders } from '../registry.js'
import '../register-providers.js'
import { refreshEnabled } from '../orchestrator.js'
import { loadGeniusFallPrefs, setProviderEnabled } from '../storage.js'
import type { MetricSection, ProviderSnapshot } from '../types.js'
import { MetricValueView } from './metric-value.js'
import { isPersonalQuotaFallen } from '../quota-fallen.js'

const SECTION_ORDER: MetricSection[] = ['summary', 'billing', 'team', 'details']

function sectionLabel(section: MetricSection, t: (k: string) => string): string {
  return t(`options.geniusFall.section.${section}`)
}

function snapQuotaFallen(snap: ProviderSnapshot): boolean {
  const spend = snap.metrics.find((m) => m.def.id === 'spend')?.value
  if (spend?.kind !== 'currency') return false
  return isPersonalQuotaFallen({
    percentUsed: spend.percentUsed,
    remainingUsd: spend.remainingUsd,
    spentUsd: spend.spentUsd,
    limitUsd: spend.limitUsd,
  })
}

export function GeniusFallPanel() {
  const { t } = useI18n()
  const providers = useMemo(() => listQuotaProviders(), [])
  const [enabledIds, setEnabledIds] = useState<string[]>(['cursor'])
  const [snapshots, setSnapshots] = useState<ProviderSnapshot[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async (ids: string[]) => {
    setLoading(true)
    setError(null)
    try {
      const next = await refreshEnabled(ids)
      setSnapshots(next)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadGeniusFallPrefs().then((prefs) => {
      setEnabledIds(prefs.enabledIds)
      void refresh(prefs.enabledIds)
    })
  }, [refresh])

  const toggleProvider = async (id: string, on: boolean) => {
    const prefs = await setProviderEnabled(id, on)
    setEnabledIds(prefs.enabledIds)
    if (on) void refresh(prefs.enabledIds)
    else setSnapshots((prev) => prev.filter((s) => s.providerId !== id))
  }

  const snapshotById = useMemo(() => {
    const map = new Map<string, ProviderSnapshot>()
    for (const s of snapshots) map.set(s.providerId, s)
    return map
  }, [snapshots])

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">{t('options.geniusFall.eyebrow')}</p>
          <h1>{t('options.geniusFall.title')}</h1>
          <p className="lede">{t('options.geniusFall.description')}</p>
        </div>
        <button
          type="button"
          className="button primary"
          disabled={loading || enabledIds.length === 0}
          onClick={() => void refresh(enabledIds)}
        >
          {loading ? t('options.geniusFall.refreshing') : t('options.geniusFall.refresh')}
        </button>
      </header>

      {error ? (
        <div className="notice" role="alert">
          {error}
        </div>
      ) : null}

      <section className="panel-block">
        <h2>{t('options.geniusFall.platformsTitle')}</h2>
        <p className="hint">{t('options.geniusFall.platformsHint')}</p>
        <div className="gf-platform-list">
          {providers.map((provider) => {
            const enabled = enabledIds.includes(provider.id)
            return (
              <label key={provider.id} className="gf-platform-row">
                <span>
                  <strong>{provider.label}</strong>
                  <small>{provider.description}</small>
                  {!provider.implemented ? (
                    <span className="gf-badge gf-badge-muted">{t('options.geniusFall.comingSoon')}</span>
                  ) : null}
                </span>
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => void toggleProvider(provider.id, e.target.checked)}
                />
              </label>
            )
          })}
        </div>
      </section>

      {enabledIds.map((id) => {
        const provider = providers.find((p) => p.id === id)
        if (!provider) return null
        const snap = snapshotById.get(id)
        return (
          <section key={id} className="panel-block gf-provider-card">
            <div className="gf-provider-head">
              <h2>{provider.label}</h2>
              {snap?.fetchedAt ? (
                <small className="gf-muted">
                  {t('options.geniusFall.updatedAt')}{' '}
                  {new Date(snap.fetchedAt).toLocaleString()}
                </small>
              ) : null}
            </div>

            {!provider.implemented ? (
              <p className="gf-empty">{t('options.geniusFall.stubEmpty')}</p>
            ) : snap?.ok === false ? (
              <div className="gf-empty">
                <p>{snap.error ?? t('options.geniusFall.fetchFailed')}</p>
                <small>{provider.connectionHint()}</small>
              </div>
            ) : snap ? (
              <>
                {snapQuotaFallen(snap) ? (
                  <div className="gf-fallen-panel" role="status">
                    <div className="gf-fallen-panel-emoji" aria-hidden="true">
                      😭 💀 😭
                    </div>
                    <p className="gf-fallen-panel-title">{t('options.geniusFall.fallenTitle')}</p>
                    <p className="gf-fallen-panel-hint">{t('options.geniusFall.fallenHint')}</p>
                  </div>
                ) : null}
                {SECTION_ORDER.map((section) => {
                const rows = snap.metrics
                  .filter((m) => m.def.section === section && m.value)
                  .sort((a, b) => (a.def.order ?? 0) - (b.def.order ?? 0))
                if (!rows.length) return null
                return (
                  <div key={section} className="gf-section">
                    <h3>{sectionLabel(section, t)}</h3>
                    <div className="metric-grid">
                      {rows.map(({ def, value }) => (
                        <article key={def.id} className="metric gf-metric">
                          <span>{def.title}</span>
                          {value ? <MetricValueView value={value} /> : null}
                        </article>
                      ))}
                    </div>
                  </div>
                )
              })}
              </>
            ) : loading ? (
              <p className="gf-muted">{t('options.geniusFall.loading')}</p>
            ) : null}
          </section>
        )
      })}
    </>
  )
}
