import type { RecipePlane, TaskIntent } from '@naviforge/runtime'
import type { ToolResult } from '@naviforge/shared'

import { bumpRecipeSuccess, resolveRecipeForUrl, saveRecipe } from './site-recipe-store'

export function createChromeRecipePlane(getTabId: () => number): RecipePlane {
  return {
    async find(_host: string, intent: TaskIntent) {
      const tab = await chrome.tabs.get(getTabId())
      const url = tab.url ?? ''
      return resolveRecipeForUrl(url, intent)
    },
    async save(recipe) {
      await saveRecipe(recipe)
      return { ok: true, data: { id: recipe.id } } satisfies ToolResult<{ id: string }>
    },
    async bumpSuccess(id: string) {
      await bumpRecipeSuccess(id)
    },
  }
}
