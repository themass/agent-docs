export function hostFromUrl(url) {
    try {
        return new URL(url).hostname;
    }
    catch {
        return undefined;
    }
}
export function recipeHostMatches(recipe, host) {
    if (!host)
        return false;
    return recipe.hosts.some((pattern) => pattern === '*' ||
        host === pattern ||
        host.endsWith(`.${pattern}`) ||
        pattern.startsWith('*.') && host.endsWith(pattern.slice(1)));
}
export function findSiteRecipe(recipes, host, intent) {
    const matches = recipes.filter((recipe) => recipe.intent === intent && recipeHostMatches(recipe, host));
    return matches.sort((a, b) => {
        const rank = (recipe) => recipe.source === 'user' ? 0 : recipe.source === 'learned' ? 1 : 2;
        const ra = rank(a);
        const rb = rank(b);
        if (ra !== rb)
            return ra - rb;
        return (b.successCount ?? 0) - (a.successCount ?? 0);
    })[0];
}
