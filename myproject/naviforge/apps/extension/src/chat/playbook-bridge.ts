import { runPlaybook, type Playbook } from '@naviforge/playbook'

import { createChromeDomPlane } from '../lib/chrome-dom-plane'
import { createChromeNetworkPlane } from '../lib/chrome-network-plane'
import { observeFromPlaybook } from '../lib/playbook-observe'

export async function observePlaybook(
  tabId: number,
  playbook: Playbook,
  inputs: Record<string, string>
) {
  return observeFromPlaybook(tabId, playbook, inputs)
}

/** Execute a saved playbook without involving the agent loop or LLM. */
export async function replayPlaybookRun(options: {
  tabId: number
  playbook: Playbook
  inputs: Record<string, string>
  networkEnabled: boolean
  captureNetworkBodies: boolean
}) {
  const network = options.networkEnabled
    ? createChromeNetworkPlane(() => options.tabId, {
        captureBodies: options.captureNetworkBodies,
      })
    : undefined
  let networkMessage: string | undefined
  if (network) {
    const started = await network.start()
    if (!started.ok) networkMessage = `network attach skipped: ${started.error.message}`
  }
  try {
    const result = await runPlaybook(
      createChromeDomPlane(() => options.tabId),
      options.playbook,
      options.inputs,
      network
    )
    return { ...result, networkMessage }
  } finally {
    if (network) await network.stop()
  }
}
