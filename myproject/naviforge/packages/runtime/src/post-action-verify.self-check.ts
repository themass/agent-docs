import assert from 'node:assert/strict'

import type { DomSnapshot } from '@naviforge/dom-plane'

import type { AgentCtx } from './agent-ctx.js'
import { buildTaskContract } from './task-contract.js'
import { createRuntimeState, reduceRuntimeState } from './runtime-state.js'
import { transitionCapability, capabilityUsable, capabilityRetryable } from './capability-state.js'
import { attachPageState } from './pi-run-loop.js'
import {
  captureActionBaseline,
  verifyActionEffect,
  clickAndVerify,
  isKnownInertCandidate,
} from './post-action-verify.js'

function baseSnap(overrides: Partial<DomSnapshot> = {}): DomSnapshot {
  return {
    revision: 1,
    url: 'https://example.test/home',
    title: 'Home',
    header: '',
    content: '*[5]<img />\ntitle a',
    footer: '',
    ...overrides,
  }
}

function makeCtx(snap: DomSnapshot, overrides: Record<string, unknown> = {}): AgentCtx {
  const contract = buildTaskContract('分析这个页面里的视频，名称和播放链接')
  let state = createRuntimeState(contract)
  const ctx = {
    task: '分析这个页面里的视频，名称和播放链接',
    taskContract: contract,
    gates: { deliverable: 'media' },
    snap,
    pageState: { url: snap.url, title: snap.title, role: 'list', blocked: false, items: [] },
    runtimeState: state,
    metadata: {},
    agent: { planes: { dom: {}, network: undefined } },
    createRecord: (type: string, payload: unknown) => ({ type, payload, at: Date.now() }),
    emit: () => undefined,
    recordNote: () => undefined,
    recordEvidence: (input: { kind: 'page' | 'dom' | 'network' | 'tool' | 'user' | 'artifact'; source: string; summary: string; confidence?: number; data?: unknown }) => {
      state = reduceRuntimeState(state, { type: 'evidence', evidence: input })
      ;(ctx as unknown as { runtimeState: unknown }).runtimeState = state
    },
    syncRuntimePageState: () => undefined,
    ...overrides,
  }
  return ctx as unknown as AgentCtx
}

// --- 1. Capability-state is the single source of truth: no parallel
// `metadata.networkDegraded` flag exists any more; `networkUnavailable`
// and `networkRetrySoon` must agree with `runtimeState.capabilities.network`.
{
  const ctx = makeCtx(baseSnap())
  assert.equal((ctx as any).metadata.networkDegraded, undefined, 'legacy metadata flag must not be read/written anywhere')

  let state = ctx.runtimeState
  state = { ...state, capabilities: transitionCapability(state.capabilities, 'network', 'transient_error', { retryAt: Date.now() + 10_000 }) }
  assert.equal(capabilityUsable(state.capabilities.network), false)
  assert.equal(capabilityRetryable(state.capabilities.network), false, 'retryAt in the future must not be retryable yet')

  state = { ...state, capabilities: transitionCapability(state.capabilities, 'network', 'transient_error', { retryAt: Date.now() - 1 }) }
  assert.equal(capabilityRetryable(state.capabilities.network), true, 'past retryAt must be retryable')

  state = { ...state, capabilities: transitionCapability(state.capabilities, 'network', 'unavailable') }
  assert.equal(capabilityUsable(state.capabilities.network), false)
  assert.equal(capabilityRetryable(state.capabilities.network), false, 'unavailable (hard stop) must not be retryable')
}

// --- 2. verifyActionEffect reports noEffect when nothing changed.
{
  const snap = baseSnap()
  const ctx = makeCtx(snap)
  const baseline = await captureActionBaseline(ctx)
  // Nothing changes: same url/revision/items/network.
  const verification = await verifyActionEffect(ctx, baseline)
  assert.equal(verification.noEffect, true)
  assert.equal(verification.urlChanged, false)
  assert.equal(verification.revisionChanged, false)
}

// --- 3. verifyActionEffect detects a revision change (DOM mutated in place).
{
  const snap = baseSnap()
  const ctx = makeCtx(snap)
  const baseline = await captureActionBaseline(ctx)
  ;(ctx as any).snap = { ...snap, revision: snap.revision + 1 }
  const verification = await verifyActionEffect(ctx, baseline)
  assert.equal(verification.revisionChanged, true)
  assert.equal(verification.noEffect, false)
}

// --- 4. clickAndVerify marks a no-op click as inert and will not retry it.
{
  const snap = baseSnap()
  let clickCalls = 0
  const ctx = makeCtx(snap, {
    agent: {
      planes: {
        dom: {
          click: async (index: number) => {
            clickCalls += 1
            return { ok: true, data: { clicked: true } }
          },
          wait: async () => ({ ok: true, data: { waited: true } }),
          snapshot: async () => ({ ok: true, data: snap }), // unchanged snapshot => no effect
          extractContent: async () => ({ ok: true, data: { items: [], candidates: 0 } }),
        },
        network: undefined,
      },
    },
  })
  // Establish a realistic baseline: Page State for an unchanged snapshot must
  // already reflect what attachPageState would compute, otherwise comparing
  // "before" (hand-set) vs "after" (attachPageState-derived) produces a false
  // positive new-candidate diff.
  await attachPageState(ctx)

  const first = await clickAndVerify(ctx, { index: 5 })
  assert.equal(first.ok, true)
  if (first.ok) assert.equal(first.verification.noEffect, true)
  assert.equal(isKnownInertCandidate(ctx, snap.url, 5), true, 'a no-effect click must be remembered as inert')

  const second = await clickAndVerify(ctx, { index: 5 })
  assert.equal(second.ok, false)
  if (!second.ok) assert.equal(second.reason, 'already_inert')
  assert.equal(clickCalls, 1, 'must not click the same inert index twice')
}

// --- 5. clickAndVerify reports a real effect when the snapshot changes.
{
  const snap = baseSnap()
  const changed = baseSnap({ revision: snap.revision + 1, url: 'https://example.test/detail/1' })
  let afterClick = false
  const ctx = makeCtx(snap, {
    agent: {
      planes: {
        dom: {
          click: async () => {
            afterClick = true
            return { ok: true, data: { clicked: true } }
          },
          wait: async () => ({ ok: true, data: { waited: true } }),
          snapshot: async () => ({ ok: true, data: afterClick ? changed : snap }),
          extractContent: async () => ({ ok: true, data: { items: [], candidates: 0 } }),
        },
        network: undefined,
      },
    },
  })
  // Establish a realistic baseline for the pre-click snapshot before clicking.
  await attachPageState(ctx)

  const result = await clickAndVerify(ctx, { index: 5 })
  assert.equal(result.ok, true)
  if (result.ok) {
    assert.equal(result.verification.urlChanged, true)
    assert.equal(result.verification.revisionChanged, true)
    assert.equal(result.verification.noEffect, false)
  }
  assert.equal(isKnownInertCandidate(ctx, snap.url, 5), false, 'a click with a real effect must not be marked inert')
}

console.log('post-action-verify.self-check ok')
