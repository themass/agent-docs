export type WorkspaceRunOutcome = {
  kind: 'success' | 'failed' | 'blocked' | 'cancelled' | 'waiting'
  title: string
  message: string
  /** Opens options.html#section when user clicks the CTA in the agent UI. */
  optionsSection?: string
}
