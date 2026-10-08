import assert from 'node:assert/strict';
import { findSiteRecipe, hostFromUrl, recipeHostMatches } from './site-recipe.js';
const recipes = [
    {
        id: 'a',
        title: 'host',
        hosts: ['wenku.baidu.com'],
        intent: 'page_download',
        version: 1,
        source: 'learned',
        steps: [],
        successCount: 2,
    },
    {
        id: 'b',
        title: 'wildcard',
        hosts: ['*'],
        intent: 'media_extract',
        version: 1,
        source: 'bundled',
        steps: [{ use: 'page_signals_playback' }],
    },
];
assert.equal(hostFromUrl('https://wenku.baidu.com/view/1'), 'wenku.baidu.com');
assert.ok(recipeHostMatches(recipes[0], 'wenku.baidu.com'));
assert.equal(findSiteRecipe(recipes, 'wenku.baidu.com', 'page_download')?.id, 'a');
assert.equal(findSiteRecipe(recipes, 'foo.com', 'media_extract')?.id, 'b');
console.log('site-recipe self-check ok');
