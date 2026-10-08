import type { RecordedDomAction } from '@naviforge/playbook'
import type { RecipeStep, SiteRecipe, TaskIntent } from '@naviforge/runtime'
import { hostFromUrl, resolveTaskIntent } from '@naviforge/runtime'

import { saveRecipe } from './site-recipe-store'

function urlIncludesForNetwork(url: string): string {
  if (url.includes('.m3u8')) return '.m3u8'
  if (url.includes('.mp4')) return '.mp4'
  if (url.includes('.webm')) return '.webm'
  try {
    const path = new URL(url).pathname
    const tail = path.split('/').filter(Boolean).pop()
    if (tail && tail.length <= 48) return tail
  } catch {
    /* ignore */
  }
  return url.slice(0, 40)
}

export function recipeStepsFromRecordedActions(
  actions: RecordedDomAction[],
  intent: TaskIntent
): RecipeStep[] {
  const domActions = actions.filter(
    (action) => action.tool === 'dom_click' || action.tool === 'dom_type'
  )
  if (!domActions.length && intent !== 'media_extract') return []

  const steps: RecipeStep[] = []
  if (intent === 'media_extract') {
    steps.push({ use: 'page_signals_playback', optional: true })
  }
  steps.push({ use: 'dom_snapshot', mode: 'compact' })

  for (const action of domActions) {
    if (action.tool === 'dom_click') {
      steps.push(
        action.selector
          ? { use: 'dom_click', selector: action.selector }
          : { use: 'dom_click', textIncludes: '下载', optional: true }
      )
      if (action.network?.url) {
        steps.push({
          use: 'network_wait',
          urlIncludes: urlIncludesForNetwork(action.network.url),
          timeout_ms: intent === 'media_extract' ? 20_000 : 15_000,
        })
      }
    }
  }

  if (intent === 'page_download') {
    steps.push({ use: 'dom_wait', kind: 'download', timeout_ms: 60_000, optional: true })
  }

  return steps
}

export async function learnSiteRecipeFromRun(opts: {
  task: string
  url?: string
  recordedActions: RecordedDomAction[]
}): Promise<SiteRecipe | null> {
  const intent = resolveTaskIntent(opts.task)
  if (intent !== 'page_download' && intent !== 'media_extract') return null
  const host = opts.url ? hostFromUrl(opts.url) : undefined
  if (!host) return null

  const steps = recipeStepsFromRecordedActions(opts.recordedActions, intent)
  if (steps.length < 2) return null

  const recipe: SiteRecipe = {
    id: `learned-${intent}-${host.replace(/\./g, '-')}`,
    title: `${host} · ${intent === 'media_extract' ? '媒体' : '下载'}`,
    hosts: [host],
    intent,
    version: 1,
    source: 'learned',
    steps,
    createdAt: Date.now(),
  }
  await saveRecipe(recipe)
  return recipe
}
