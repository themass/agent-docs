export type TabWorkspace = {
  task: string
  activeThreadId: string
  traceOpen: boolean
  targetTab: { id: number; url?: string; title?: string } | null
}

export type TabWorkspaces = Record<string, TabWorkspace>

export function canRestoreTabWorkspace(opts: {
  generation: number
  currentGeneration: number
  running: boolean
  resumeLocked: boolean
  hasResumeRequest: boolean
}): boolean {
  return (
    opts.generation === opts.currentGeneration &&
    !opts.running &&
    !opts.resumeLocked &&
    !opts.hasResumeRequest
  )
}

export function readTabWorkspace(
  workspaces: TabWorkspaces,
  tabId: number
): TabWorkspace | undefined {
  return workspaces[String(tabId)]
}

export function writeTabWorkspace(
  workspaces: TabWorkspaces,
  tabId: number,
  workspace: TabWorkspace
): TabWorkspaces {
  return { ...workspaces, [String(tabId)]: workspace }
}
