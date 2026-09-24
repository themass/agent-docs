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
    'dom_snapshot',
    'dom_read',
    'tabs_open',
    'tabs_switch',
    'tabs_close',
    'network_read',
    'fetch_text',
    'web_search',
    'system_done',
  ],
  allowReadonlyMcp: true,
  manageNetwork: false,
}
