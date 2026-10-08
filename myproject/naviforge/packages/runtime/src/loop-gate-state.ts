import type { ListOpenHint } from './run-limits.js'
import type { PageVisit } from './page-cache.js'
import { bareSkillId } from './task-classifier.js'
import { createActionLoopGate, type ActionLoopGate } from './loop-gates.js'

export type RunTabSummary = {
  id: number
  url?: string
  title?: string
  active: boolean
  windowId?: number
}

/** Per-run gate state for observation dedupe, action loops, and skill stickiness. */
export type AgentGates = {
  loadedSkillIds: Set<string>
  loadedSkillBodies: string[]
  jsCspBlocked: Set<string>
  seenObs: Set<string>
  lastObsByKey: Map<string, string>
  dupSkipByKey: Map<string, number>
  actionLoop: ActionLoopGate
  lastListHints: ListOpenHint[]
  taskHintIssued: boolean
  /** Consecutive tool steps without a new observation key (loop guard). */
  stepsWithoutNewObs: number
  /** HITL already issued per url+friction kind (avoid repeat captcha prompts). */
  frictionHitlKeys: Set<string>
  lastPageFriction?: { url: string; report: import('./page-friction/types.js').PageFrictionReport; at: number }
  /** Tabs opened or switched to during this run (for scoped tabs_list). */
  runTabIds: Set<number>
  /** Readonly subtasks returned usable evidence. */
  subtaskEvidenceReady: boolean
  /** First tabs_list per run counts as progress; repeats do not. */
  tabsListProgressUsed: boolean
  /** URL fingerprints visited this run (tabs_open / dom_read). */
  pageVisits: Map<string, PageVisit>
  /** Resolved once per run for intent routing. */
  taskIntent?: import('./task-intent.js').TaskIntent
  /** Primary deliverable narrative (Phase A). */
  deliverable?: import('./deliverable.js').Deliverable
  scriptLoginAskIssued?: boolean
  /** Successful script_save this run (Phase C verify). */
  scriptSaved?: boolean
  scriptSavePath?: string
  /** SiteRecipe preflight succeeded without LLM. */
  recipeUsed?: boolean
  recipeId?: string
  /** Passive browser_observe extract/read returning empty (media milestone). */
  mediaPassiveObserveEmpty?: number
  /**
   * Generic click targets (keyed `${url}#${index}`) that produced no
   * observable effect (no URL/DOM/Page-State/Network change). Any
   * click-and-check flow should consult this before retrying an index.
   * See post-action-verify.ts.
   */
  inertActionIndexes?: Set<string>
  /**
   * `(url, snapshot revision)` PAGE STATE was last computed for. Lets
   * attachPageState skip recompute + duplicate PAGE STATE note emission
   * when called again with nothing changed (e.g. once at run start, once
   * more from PreflightHook — both before any navigation/click happens).
   */
  lastPageStateFor?: { url: string; revision: number }
}

export function createAgentGates(sameActionLimit: number): AgentGates {
  return {
    loadedSkillIds: new Set(),
    loadedSkillBodies: [],
    jsCspBlocked: new Set(),
    seenObs: new Set(),
    lastObsByKey: new Map(),
    dupSkipByKey: new Map(),
    actionLoop: createActionLoopGate(sameActionLimit),
    lastListHints: [],
    taskHintIssued: false,
    stepsWithoutNewObs: 0,
    frictionHitlKeys: new Set(),
    runTabIds: new Set(),
    subtaskEvidenceReady: false,
    tabsListProgressUsed: false,
    pageVisits: new Map(),
  }
}

export function resetTurnGates(gates: AgentGates): void {
  gates.lastListHints = []
  gates.taskHintIssued = false
}

export function markObservationSeen(gates: AgentGates, key: string, trace: string): void {
  gates.seenObs.add(key)
  gates.lastObsByKey.set(key, trace)
}

export function observationAlreadySeen(gates: AgentGates, key: string | null): boolean {
  return Boolean(key && gates.seenObs.has(key))
}

export function bumpDuplicateSkip(gates: AgentGates, key: string): number {
  const n = (gates.dupSkipByKey.get(key) ?? 0) + 1
  gates.dupSkipByKey.set(key, n)
  return n
}

export function priorObservation(gates: AgentGates, key: string): string | undefined {
  return gates.lastObsByKey.get(key)
}

export function recordListHints(gates: AgentGates, hints: ListOpenHint[]): void {
  if (hints.length) gates.lastListHints = hints
}

export function recordLoadedSkill(gates: AgentGates, id: string, body?: string): void {
  gates.loadedSkillIds.add(bareSkillId(id))
  if (body?.trim()) {
    gates.loadedSkillBodies.length = 0
    gates.loadedSkillBodies.push(body.trim().slice(0, 4_000))
  }
}

export function recordRunTab(gates: AgentGates, tabId: number): void {
  if (Number.isFinite(tabId) && tabId > 0) gates.runTabIds.add(tabId)
}

/** Enough material to synthesize an answer without more tabs_list loops. */
export function hasSynthesisEvidence(gates: AgentGates): boolean {
  if (gates.subtaskEvidenceReady) return true
  for (const key of gates.seenObs) {
    if (key.startsWith('dom_read|') || key.startsWith('fetch_text|')) return true
  }
  return false
}

export function scopeTabsToRun(
  tabs: RunTabSummary[],
  gates: AgentGates,
  anchorTabId?: number
): { tabs: RunTabSummary[]; scoped: boolean; totalBrowserTabs: number; hint: string } {
  const totalBrowserTabs = tabs.length
  const ids = new Set(gates.runTabIds)
  if (anchorTabId != null) ids.add(anchorTabId)
  if (!ids.size) {
    const active = tabs.filter((tab) => tab.active).slice(0, 1)
    return {
      tabs: active,
      scoped: false,
      totalBrowserTabs,
      hint: '先用 tabs_open(url) 打开来源页，再 tabs_switch(tab_id) + dom_read(body)；勿反复 tabs_list。',
    }
  }
  const filtered = tabs.filter((tab) => ids.has(tab.id))
  return {
    tabs: filtered.length ? filtered : tabs.filter((tab) => tab.active).slice(0, 1),
    scoped: true,
    totalBrowserTabs,
    hint: '仅本 run 相关 tab。用 tabs_switch(tab_id) 切换后 dom_read(body)；已有子任务/dom_read 证据可直接 system_done。',
  }
}
