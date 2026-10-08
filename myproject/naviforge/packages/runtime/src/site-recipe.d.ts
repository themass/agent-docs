import type { TaskIntent } from './task-intent.js';
type RecipeStepBase = {
    optional?: boolean;
};
export type RecipeStep = ({
    use: 'dom_snapshot';
    mode?: 'compact' | 'viewport' | 'full';
} & RecipeStepBase) | ({
    use: 'dom_click';
    textIncludes?: string;
    selector?: string;
} & RecipeStepBase) | ({
    use: 'dom_wait';
    kind: 'download' | 'stable' | 'text' | 'network_idle';
    text?: string;
    timeout_ms?: number;
} & RecipeStepBase) | ({
    use: 'network_wait';
    urlIncludes: string;
    timeout_ms?: number;
} & RecipeStepBase)
/** Try PAGE SIGNALS resolved playback (no click). */
 | ({
    use: 'page_signals_playback';
} & RecipeStepBase);
export type SiteRecipe = {
    id: string;
    title: string;
    hosts: string[];
    intent: TaskIntent;
    version: number;
    steps: RecipeStep[];
    source: 'bundled' | 'learned' | 'user';
    successCount?: number;
    lastSuccessAt?: number;
    createdAt?: number;
};
export declare function hostFromUrl(url: string): string | undefined;
export declare function recipeHostMatches(recipe: SiteRecipe, host: string): boolean;
export declare function findSiteRecipe(recipes: readonly SiteRecipe[], host: string, intent: TaskIntent): SiteRecipe | undefined;
export {};
