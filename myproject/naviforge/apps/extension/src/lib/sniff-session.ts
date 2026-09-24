const sessions = new Map<number, { projectId: string }>()

export function startSniffSession(projectId: string, tabId: number): void {
  sessions.set(tabId, { projectId })
}

export function stopSniffSession(tabId: number): string | undefined {
  const session = sessions.get(tabId)
  sessions.delete(tabId)
  return session?.projectId
}

export function getSniffSession(tabId: number): { projectId: string } | undefined {
  return sessions.get(tabId)
}

export function listSniffSessionTabIds(): number[] {
  return [...sessions.keys()]
}
