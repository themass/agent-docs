/**
 * Generic "did this click actually do anything" check.
 *
 * Runtime problem this solves: a model (or a deterministic candidate-click
 * helper) can click a DOM index that *looks* like a card/tile and treat the
 * click as progress, even when the page did not change at all (dead
 * element, overlay no-op, SPA swallowed the event). Without this, callers
 * either (a) wrongly assume the click opened a detail view and move on to
 * read evidence that never materialized, or (b) retry the exact same
 * useless index forever.
 *
 * This module is deliverable-agnostic: it only knows about URL, DOM
 * snapshot revision, Page State items, and Network event counts. Any task
 * that performs a click-and-check flow (media, forms, pagination, …) can
 * reuse it. No site/domain-specific logic belongs here.
 */

import type { AgentCtx } from './agent-ctx.js'
import { snapshotWithRetry } from './exec-turn.js'
import { attachPageState } from './pi-run-loop.js'

export type ActionBaseline = {
  url: string
  revision: number
  itemKeys: Set<string>
  networkEventCount: number
}

export type ActionVerification = {
  urlChanged: boolean
  revisionChanged: boolean
  newCandidatesFound: boolean
  networkActivityObserved: boolean
  /** True when none of the above changed — the action was very likely a no-op. */
  noEffect: boolean
}

function pageStateItemKey(item: { title: string; url?: string; clickIndex?: number }): string {
  return `${item.clickIndex ?? ''}|${item.url ?? ''}|${item.title}`
}

function currentItemKeys(ctx: AgentCtx): Set<string> {
  return new Set((ctx.pageState?.items ?? []).map(pageStateItemKey))
}

async function currentNetworkEventCount(ctx: AgentCtx): Promise<number> {
  const network = ctx.agent.planes.network
  if (!network) return 0
  const digest = await network.digest(1)
  return digest.ok ? digest.data.count : 0
}

/** Snapshot the state we need to diff *before* performing a click. */
export async function captureActionBaseline(ctx: AgentCtx): Promise<ActionBaseline> {
  return {
    url: ctx.snap.url,
    revision: ctx.snap.revision,
    itemKeys: currentItemKeys(ctx),
    networkEventCount: await currentNetworkEventCount(ctx),
  }
}

/**
 * Compare current ctx state against a baseline captured before the action.
 * Caller is responsible for re-snapshotting DOM and re-running
 * `attachPageState` first (see `clickAndVerify` for the common path).
 */
export async function verifyActionEffect(
  ctx: AgentCtx,
  baseline: ActionBaseline
): Promise<ActionVerification> {
  const urlChanged = ctx.snap.url !== baseline.url
  const revisionChanged = ctx.snap.revision !== baseline.revision
  const nowKeys = currentItemKeys(ctx)
  const newCandidatesFound = [...nowKeys].some((key) => !baseline.itemKeys.has(key))
  const networkEventCount = await currentNetworkEventCount(ctx)
  const networkActivityObserved = networkEventCount > baseline.networkEventCount
  const noEffect = !urlChanged && !revisionChanged && !newCandidatesFound && !networkActivityObserved
  return { urlChanged, revisionChanged, newCandidatesFound, networkActivityObserved, noEffect }
}

/** Stable key for "have we already tried clicking this index on this page and seen nothing happen". */
export function inertCandidateKey(url: string, index: number): string {
  return `${url}#${index}`
}

export function isKnownInertCandidate(ctx: AgentCtx, url: string, index: number): boolean {
  return ctx.gates.inertActionIndexes?.has(inertCandidateKey(url, index)) ?? false
}

export function markInertCandidate(ctx: AgentCtx, url: string, index: number): void {
  if (!ctx.gates.inertActionIndexes) ctx.gates.inertActionIndexes = new Set()
  ctx.gates.inertActionIndexes.add(inertCandidateKey(url, index))
}

export type ClickAndVerifyOptions = {
  /** Snapshot index to click. */
  index: number
  /** Extra settle wait after click, before re-snapshot (ms). Default: rely on dom.wait network_idle. */
  waitTimeoutMs?: number
}

export type ClickAndVerifyResult =
  | { ok: true; verification: ActionVerification }
  | { ok: false; reason: 'already_inert' | 'click_failed' | 'dom_unavailable'; message?: string }

/**
 * Generic click-then-verify primitive: click a snapshot index, let the page
 * settle, re-snapshot, rebuild Page State, then diff against the
 * pre-click baseline. Marks the candidate as inert (so callers should not
 * retry the same index on the same URL) when nothing observably changed.
 *
 * Does not know what the caller is trying to achieve — it only reports
 * whether the click had any observable effect. Callers (e.g. the media
 * candidate harvester) decide what to do next (try a different candidate,
 * look for a secondary play control, ask the model to replan, etc).
 */
export async function clickAndVerify(
  ctx: AgentCtx,
  opts: ClickAndVerifyOptions
): Promise<ClickAndVerifyResult> {
  const { dom } = ctx.agent.planes
  if (!dom.click) return { ok: false, reason: 'dom_unavailable' }

  const urlBefore = ctx.snap.url
  if (isKnownInertCandidate(ctx, urlBefore, opts.index)) {
    return { ok: false, reason: 'already_inert' }
  }

  const baseline = await captureActionBaseline(ctx)
  const clicked = await dom.click(opts.index, ctx.snap.revision)
  if (!clicked.ok) {
    return { ok: false, reason: 'click_failed', message: clicked.error.message }
  }

  if (dom.wait) {
    await dom.wait({ kind: 'network_idle', timeoutMs: opts.waitTimeoutMs ?? 2_500 }).catch(() => undefined)
  }

  const resnapped = await snapshotWithRetry(dom)
  if (resnapped.ok) ctx.snap = resnapped.data

  await attachPageState(ctx)

  const verification = await verifyActionEffect(ctx, baseline)
  if (verification.noEffect) {
    markInertCandidate(ctx, urlBefore, opts.index)
  }
  return { ok: true, verification }
}
