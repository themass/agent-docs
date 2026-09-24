import type { TaskIntent } from './task-intent.js'

type RecipeStepBase = { optional?: boolean }

export type RecipeStep =
  | ({ use: 'dom_snapshot'; mode?: 'compact' | 'viewport' | 'full' } & RecipeStepBase)
  | ({ use: 'dom_click'; textIncludes?: string; selector?: string } & RecipeStepBase)
  | ({
      use: 'dom_wait'
      kind: 'download' | 'stable' | 'text' | 'network_idle'
      text?: string
      timeout_ms?: number
    } & RecipeStepBase)
  | ({ use: 'network_wait'; urlIncludes: string; timeout_ms?: number } & RecipeStepBase)
  /** Try PAGE SIGNALS resolved playback (no click). */
  | ({ use: 'page_signals_playback' } & RecipeStepBase)

export type SiteRecipe = {
  id: string
  title: string
  hosts: string[]
  intent: TaskIntent
  version: number
  steps: RecipeStep[]
  source: 'bundled' | 'learned' | 'user'
  successCount?: number
  lastSuccessAt?: number
  createdAt?: number
}

export function hostFromUrl(url: string): string | undefined {
  try {
    return new URL(url).hostname
  } catch {
    return undefined
  }
}

export function recipeHostMatches(recipe: SiteRecipe, host: string): boolean {
  if (!host) return false
  return recipe.hosts.some(
    (pattern) =>
      pattern === '*' ||
      host === pattern ||
      host.endsWith(`.${pattern}`) ||
      pattern.startsWith('*.') && host.endsWith(pattern.slice(1))
  )
}

export function findSiteRecipe(
  recipes: readonly SiteRecipe[],
  host: string,
  intent: TaskIntent
): SiteRecipe | undefined {
  const matches = recipes.filter((recipe) => recipe.intent === intent && recipeHostMatches(recipe, host))
  return matches.sort((a, b) => {
    const rank = (recipe: SiteRecipe) =>
      recipe.source === 'user' ? 0 : recipe.source === 'learned' ? 1 : 2
    const ra = rank(a)
    const rb = rank(b)
    if (ra !== rb) return ra - rb
    return (b.successCount ?? 0) - (a.successCount ?? 0)
  })[0]
}
