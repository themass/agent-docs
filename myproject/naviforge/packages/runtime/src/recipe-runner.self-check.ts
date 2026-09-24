import assert from 'node:assert/strict'

import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'

import { runSiteRecipe } from './recipe-runner.js'
import type { SiteRecipe } from './site-recipe.js'

const snap: DomSnapshot = {
  revision: 1,
  url: 'https://example.com/play',
  title: 'play',
  header: '',
  content: '[3] <button> 播放\n[4] <a> home',
  footer: '',
}

const dom: DomPlane = {
  async snapshot() {
    return { ok: true, data: snap }
  },
  async click(index, revision) {
    assert.equal(index, 3)
    assert.equal(revision, 1)
    return { ok: true, data: { message: 'clicked' } }
  },
  async wait() {
    return { ok: true, data: { message: 'ok' } }
  },
}

const recipe: SiteRecipe = {
  id: 'test-click',
  title: 'click play',
  hosts: ['example.com'],
  intent: 'media_extract',
  version: 1,
  source: 'bundled',
  steps: [
    { use: 'dom_click', textIncludes: '播放' },
    { use: 'dom_wait', kind: 'stable', timeout_ms: 1000 },
  ],
}

const result = await runSiteRecipe({
  recipe,
  dom,
  task: '播放地址',
  url: snap.url,
  snap,
})
assert.ok(result.ok)

console.log('recipe-runner self-check ok')
