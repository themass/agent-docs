import { runPlaybook, type Playbook } from '@naviforge/playbook'
import type { DomSnapshot } from '@naviforge/dom-plane'

import { createChromeDomPlane } from './chrome-dom-plane'

export type PlaybookObserveResult = {
  playbookOk: boolean
  traces: string[]
  error?: string
  snapshot: DomSnapshot | null
}

/** Replay a playbook deterministically, then snapshot for agent re-observe (failed-run recovery). */
export async function observeFromPlaybook(
  tabId: number,
  playbook: Playbook,
  inputs: Record<string, string> = {}
): Promise<PlaybookObserveResult> {
  const dom = createChromeDomPlane(() => tabId)
  const run = await runPlaybook(dom, playbook, inputs)
  const snap = await dom.snapshot()
  return {
    playbookOk: run.ok,
    traces: run.traces,
    error: run.error,
    snapshot: snap.ok ? snap.data : null,
  }
}
