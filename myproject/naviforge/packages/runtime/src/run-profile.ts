export type RunProfile = {
  name: 'readonly-child'
  allowedTools: readonly string[]
  allowReadonlyMcp?: boolean
  /** Parent owns the network debugger lifecycle. */
  manageNetwork?: boolean
}

export const READONLY_RUN_PROFILE: RunProfile = {
  name: 'readonly-child',
  allowedTools: [
    'browser_observe',
    'tabs',
    'network',
    'fetch_text',
    'web_search',
    'system_done',
  ],
  allowReadonlyMcp: true,
  manageNetwork: false,
}
