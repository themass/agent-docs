/** Raw page artifacts collected in the content script (before signal mining). */
export type PageSignalCollectPayload = {
  url: string
  title: string
  inlineScripts: string[]
  externalScriptSrcs: string[]
  meta: Array<{ name?: string; property?: string; content: string }>
  resources: Array<{ tag: string; attr: string; value: string }>
  /** B3: inline / computed background-image and similar CSS hints. */
  styleResources?: Array<{ tag: string; property: string; value: string }>
  /** F2: same-origin script bodies fetched in content script. */
  fetchedScriptBodies?: Array<{ url: string; preview: string }>
  /** F3: inline scripts from same-origin iframes. */
  iframeInlineScripts?: string[]
}

export type PageSignalKind =
  | 'inline_config'
  | 'url_literal'
  | 'dom_resource'
  | 'meta'
  | 'network'
  | 'resolved'
  | 'style'
  | 'derived'

export type PageSignal = {
  kind: PageSignalKind
  source: string
  label: string
  value: string
  resolvedUrl?: string
  confidence: number
  reason?: string
}

export type PageSignalsBundle = {
  url: string
  signals: PageSignal[]
}
