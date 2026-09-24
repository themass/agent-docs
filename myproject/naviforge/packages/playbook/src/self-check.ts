import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'

import { forgePlaybook, runPlaybook } from './index.js'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

const snap: DomSnapshot = {
  revision: 1,
  url: 'http://localhost/test',
  title: 'Test',
  header: 'header',
  content: '[1] button "Go"\n[2] link "Video A"',
  footer: 'footer',
}

const dom: DomPlane = {
  async snapshot() {
    return { ok: true, data: snap }
  },
  async click(index) {
    return { ok: true, data: { message: `clicked ${index}` } }
  },
  async type(index, text) {
    return { ok: true, data: { message: `typed ${index} ${text}` } }
  },
}

const pb = forgePlaybook({
  title: 'demo',
  actions: [{ tool: 'dom_click', index: 1 }],
})
assert(pb, 'forge playbook')
const withAssert = {
  ...pb!,
  assertions: [{ includes: 'Video A' }],
  steps: [...pb!.steps, { id: 'a1', use: 'assert.text' as const, includes: 'Go' }],
}
const ok = await runPlaybook(dom, withAssert)
assert(ok.ok, 'playbook with assertions passes')

const fail = await runPlaybook(dom, { ...withAssert, assertions: [{ includes: 'missing text' }] })
assert(!fail.ok && fail.error?.includes('assertion'), 'playbook assertion fails')

console.log('playbook self-check ok')
