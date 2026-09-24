import type { SiteRecipe } from '@naviforge/runtime'
import { findSiteRecipe, hostFromUrl, type TaskIntent } from '@naviforge/runtime'

import { BUNDLED_RECIPES } from './bundled-recipes'
import { safeStorageLocalGet, safeStorageLocalSet } from './extension-runtime'

const KEY = 'naviforgeSiteRecipes'

export async function listLearnedRecipes(): Promise<SiteRecipe[]> {
  const saved = await safeStorageLocalGet(KEY)
  const list = saved?.[KEY] as SiteRecipe[] | undefined
  return Array.isArray(list) ? list : []
}

export async function listAllRecipes(): Promise<SiteRecipe[]> {
  const learned = await listLearnedRecipes()
  return [
    ...learned.filter((recipe) => recipe.source === 'user'),
    ...learned.filter((recipe) => recipe.source !== 'user'),
    ...BUNDLED_RECIPES,
  ]
}

export async function deleteRecipe(id: string): Promise<void> {
  const list = (await listLearnedRecipes()).filter((item) => item.id !== id)
  await safeStorageLocalSet({ [KEY]: list })
}

export async function saveRecipe(recipe: SiteRecipe): Promise<void> {
  const list = await listLearnedRecipes()
  const index = list.findIndex((item) => item.id === recipe.id)
  const next = { ...recipe, source: recipe.source === 'bundled' ? 'learned' : recipe.source }
  if (index >= 0) list[index] = next
  else list.unshift(next)
  await safeStorageLocalSet({ [KEY]: list.slice(0, 50) })
}

/** Success counter only — user-owned recipes in storage; no auto-clone from bundled. */
export async function bumpRecipeSuccess(id: string): Promise<void> {
  const list = await listLearnedRecipes()
  const recipe = list.find((item) => item.id === id)
  if (!recipe) return
  recipe.successCount = (recipe.successCount ?? 0) + 1
  recipe.lastSuccessAt = Date.now()
  await safeStorageLocalSet({ [KEY]: list })
}

export async function findLearnedRecipe(
  host: string,
  intent: TaskIntent
): Promise<SiteRecipe | undefined> {
  return findSiteRecipe(await listLearnedRecipes(), host, intent)
}

export async function resolveRecipeForUrl(
  url: string,
  intent: SiteRecipe['intent']
): Promise<SiteRecipe | undefined> {
  const host = hostFromUrl(url)
  if (!host) return undefined
  return findSiteRecipe(await listAllRecipes(), host, intent)
}
