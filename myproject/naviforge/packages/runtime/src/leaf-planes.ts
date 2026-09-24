import type { DomPlane } from '@naviforge/dom-plane'

import type { AgentOptions } from './agent.js'

/** Per-child ephemeral tab scope — parent anchor tab is never switched. */
export type LeafPlaneFactory = NonNullable<AgentOptions['createLeafPlanes']>

export type LeafPlaneBundle = {
  dom: DomPlane
  tabs?: AgentOptions['tabs']
  dispose: () => Promise<void>
}

/** Read-only DOM facade (no navigate/inject); navigation uses scoped tabs plane when provided. */
export function readonlyDom(dom: DomPlane): DomPlane {
  return {
    snapshot: () => dom.snapshot(),
    ...(dom.readPage ? { readPage: () => dom.readPage!() } : {}),
  } as DomPlane
}
