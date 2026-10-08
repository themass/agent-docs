import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane';
import type { NetworkPlane } from '@naviforge/network-plane';
import type { SiteRecipe } from './site-recipe.js';
export type RecipeRunResult = {
    ok: true;
    text: string;
    recipeId: string;
} | {
    ok: false;
    error: string;
    recoverable: boolean;
};
export declare function runSiteRecipe(opts: {
    recipe: SiteRecipe;
    dom: DomPlane;
    network?: NetworkPlane;
    task: string;
    url: string;
    snap: DomSnapshot;
}): Promise<RecipeRunResult>;
