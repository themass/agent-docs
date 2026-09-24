/** Live agent overlay + Chrome tab-group session. Written by the background SW. */
export type AgentPresence = {
  running: boolean
  tabId: number
  heartbeat: number
  task?: string
  action?: string
  /** HITL / paused: hide the lock mask so the user can use the page. */
  waiting?: boolean
}

export const PRESENCE_STALE_MS = 8_000

export const AGENT_GROUP_COLORS = [
  'blue',
  'red',
  'green',
  'yellow',
  'purple',
  'cyan',
  'orange',
  'pink',
] as const

export type AgentGroupColor = (typeof AGENT_GROUP_COLORS)[number]

export function parseAgentPresence(value: unknown): AgentPresence | undefined {
  if (!value || typeof value !== 'object') return undefined
  const rec = value as Record<string, unknown>
  if (typeof rec.running !== 'boolean' || typeof rec.tabId !== 'number' || typeof rec.heartbeat !== 'number') {
    return undefined
  }
  return {
    running: rec.running,
    tabId: rec.tabId,
    heartbeat: rec.heartbeat,
    task: typeof rec.task === 'string' ? rec.task : undefined,
    action: typeof rec.action === 'string' ? rec.action : undefined,
    waiting: rec.waiting === true,
  }
}

export function isPresenceLive(
  presence: AgentPresence | undefined,
  tabId: number,
  now = Date.now()
): boolean {
  if (!presence?.running || presence.waiting || presence.tabId !== tabId) return false
  return now - presence.heartbeat < PRESENCE_STALE_MS
}

export function formatAgentGroupTitle(task: string, maxBody = 24): string {
  const compact = task.replace(/\s+/g, ' ').trim() || 'task'
  const body = compact.length <= maxBody ? compact : `${compact.slice(0, Math.max(1, maxBody - 1))}…`
  return `NaviForge · ${body}`
}

export function colorForAgentTask(seed: string): AgentGroupColor {
  let hash = 0
  for (const char of seed) hash = (hash * 33 + char.charCodeAt(0)) >>> 0
  return AGENT_GROUP_COLORS[hash % AGENT_GROUP_COLORS.length]!
}
