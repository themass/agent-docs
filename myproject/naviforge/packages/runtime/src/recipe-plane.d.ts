import type { ToolResult } from '@naviforge/shared';
import type { SiteRecipe } from './site-recipe.js';
import type { TaskIntent } from './task-intent.js';
export interface RecipePlane {
    find(host: string, intent: TaskIntent): Promise<SiteRecipe | undefined>;
    save?(recipe: SiteRecipe): Promise<ToolResult<{
        id: string;
    }>>;
    bumpSuccess?(id: string): Promise<void>;
}
