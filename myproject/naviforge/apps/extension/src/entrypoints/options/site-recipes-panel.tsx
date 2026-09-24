import { useCallback, useEffect, useState } from 'react'
import type { SiteRecipe } from '@naviforge/runtime'
import { hostFromUrl, recipeHostMatches } from '@naviforge/runtime'

import { useI18n } from '../../i18n'
import { buildDocumentDownloadRecipe, buildMediaExtractRecipe } from '../../lib/bundled-recipes'
import {
  deleteRecipe,
  findLearnedRecipe,
  listLearnedRecipes,
  saveRecipe,
} from '../../lib/site-recipe-store'

async function activeTab(): Promise<{ host: string; url: string } | null> {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true })
  const url = tabs[0]?.url ?? ''
  if (!url.startsWith('http')) return null
  const host = hostFromUrl(url)
  if (!host) return null
  return { host, url }
}

function intentLabel(intent: SiteRecipe['intent'], t: (key: string) => string): string {
  if (intent === 'page_download') return t('options.automation.recipes.intentDownload')
  if (intent === 'media_extract') return t('options.automation.recipes.intentMedia')
  return intent
}

export function SiteRecipesPanel({
  onNotice,
  onRecipesChange,
}: {
  onNotice: (message: string) => void
  onRecipesChange?: (count: number) => void
}) {
  const { t } = useI18n()
  const [recipes, setRecipes] = useState<SiteRecipe[]>([])
  const [tabHost, setTabHost] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const reload = useCallback(async () => {
    const list = await listLearnedRecipes()
    setRecipes(list)
    onRecipesChange?.(list.length)
    const tab = await activeTab()
    setTabHost(tab?.host ?? null)
  }, [onRecipesChange])

  useEffect(() => {
    void reload()
  }, [reload])

  async function upsert(kind: 'download' | 'media', host: string): Promise<void> {
    const intent = kind === 'download' ? 'page_download' : 'media_extract'
    const existing = await findLearnedRecipe(host, intent)
    if (existing && !confirm(t('options.confirm.overwriteSiteRecipe', { host }))) return
    const recipe =
      kind === 'download' ? buildDocumentDownloadRecipe(host) : buildMediaExtractRecipe(host)
    await saveRecipe(recipe)
    await reload()
    onNotice(
      existing
        ? t('options.automation.recipes.updated', { host })
        : t('options.automation.recipes.saved', { host })
    )
  }

  async function saveFromTab(kind: 'download' | 'media'): Promise<void> {
    const tab = await activeTab()
    if (!tab) {
      onNotice(t('options.automation.recipes.needHttpTab'))
      return
    }
    setBusy(true)
    try {
      await upsert(kind, tab.host)
    } finally {
      setBusy(false)
    }
  }

  async function updateRow(recipe: SiteRecipe): Promise<void> {
    const tab = await activeTab()
    if (!tab || !recipeHostMatches(recipe, tab.host)) {
      onNotice(t('options.automation.recipes.switchTab', { host: recipe.hosts[0] ?? '' }))
      return
    }
    const kind = recipe.intent === 'page_download' ? 'download' : 'media'
    setBusy(true)
    try {
      await upsert(kind, tab.host)
    } finally {
      setBusy(false)
    }
  }

  async function remove(id: string): Promise<void> {
    if (!confirm(t('options.confirm.deleteSiteRecipe'))) return
    await deleteRecipe(id)
    await reload()
    onNotice(t('options.notice.siteRecipeDeleted'))
  }

  return (
    <div>
      <p className="field-hint" style={{ marginBottom: 12 }}>{t('options.automation.recipes.lead')}</p>

      <section className="settings-form compact" style={{ marginBottom: 16 }}>
        <strong>{t('options.automation.recipes.quickSaveTitle')}</strong>
        <p className="field-hint">
          {tabHost
            ? t('options.automation.recipes.currentTab', { host: tabHost })
            : t('options.automation.recipes.noHttpTab')}
        </p>
        <div className="button-row compact">
          <button
            type="button"
            className="button secondary"
            disabled={!tabHost || busy}
            onClick={() => void saveFromTab('download')}
          >
            {t('options.automation.recipes.saveDownload')}
          </button>
          <button
            type="button"
            className="button secondary"
            disabled={!tabHost || busy}
            onClick={() => void saveFromTab('media')}
          >
            {t('options.automation.recipes.saveMedia')}
          </button>
        </div>
      </section>

      {!recipes.length ? (
        <div className="empty">
          <strong>{t('options.automation.recipes.emptyTitle')}</strong>
          <span>{t('options.automation.recipes.emptyBody')}</span>
        </div>
      ) : (
        <div className="data-list">
          <div className="data-list-head data-list-profile">
            <span>{t('options.automation.recipes.table.intent')}</span>
            <span>{t('options.automation.recipes.table.recipe')}</span>
            <span>{t('options.automation.recipes.table.site')}</span>
            <span>{t('options.automation.profiles.table.actions')}</span>
          </div>
          {recipes.map((recipe) => {
            const canUpdate = tabHost != null && recipeHostMatches(recipe, tabHost)
            return (
              <article className="data-list-row data-list-profile" key={recipe.id}>
                <span className="data-list-badge">{intentLabel(recipe.intent, t)}</span>
                <div className="data-list-main">
                  <strong>{recipe.title}</strong>
                  <small>
                    {t('options.automation.recipes.stepsMeta', {
                      steps: String(recipe.steps.length),
                      success: String(recipe.successCount ?? 0),
                    })}
                  </small>
                </div>
                <span className="data-list-meta">{recipe.hosts.join(', ')}</span>
                <div className="data-list-actions">
                  <button
                    type="button"
                    className="text-button"
                    disabled={busy}
                    title={canUpdate ? undefined : t('options.automation.recipes.updateHint')}
                    onClick={() => void updateRow(recipe)}
                  >
                    {t('options.automation.recipes.update')}
                  </button>
                  <button type="button" className="text-button danger" onClick={() => void remove(recipe.id)}>
                    {t('options.common.buttons.delete')}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
