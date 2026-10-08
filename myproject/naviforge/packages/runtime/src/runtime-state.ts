import type { DomSnapshot } from '@naviforge/dom-plane'

import type { PageState } from './page-state.js'
import { createCapabilityRegistry, type CapabilityRegistry } from './capability-state.js'
import { createEvidenceStore, addEvidence, type EvidenceStore } from './evidence.js'
import type { TaskContract } from './task-contract.js'

export type ProgressState = {
  steps: number
  lastProgressAt: number
  lastProgressKind?: 'page' | 'dom' | 'network' | 'state' | 'artifact' | 'user'
  replanRequired: boolean
}

export type RuntimeState = {
  task: TaskContract
  page?: PageState
  snapshot?: Pick<DomSnapshot, 'revision' | 'url' | 'title'>
  capabilities: CapabilityRegistry
  evidence: EvidenceStore
  progress: ProgressState
  artifacts: Array<{ path: string; kind?: string }>
}

export type RuntimeStateEvent =
  | { type: 'page_state'; page: PageState; snapshot: Pick<DomSnapshot, 'revision' | 'url' | 'title'> }
  | { type: 'evidence'; evidence: Parameters<typeof addEvidence>[1] }
  | { type: 'progress'; kind: ProgressState['lastProgressKind']; replanRequired?: boolean }
  | { type: 'artifact'; path: string; kind?: string }

export function createRuntimeState(task: TaskContract, capabilities?: CapabilityRegistry): RuntimeState {
  return {
    task,
    capabilities: capabilities ?? createCapabilityRegistry(),
    evidence: createEvidenceStore(),
    progress: { steps: 0, lastProgressAt: Date.now(), replanRequired: false },
    artifacts: [],
  }
}

export function reduceRuntimeState(state: RuntimeState, event: RuntimeStateEvent): RuntimeState {
  switch (event.type) {
    case 'page_state': {
      const alreadyRecorded = state.evidence.records.some(
        (item) =>
          item.source === 'page_state' &&
          typeof item.data === 'object' &&
          item.data !== null &&
          (item.data as { revision?: number; url?: string }).revision === event.snapshot.revision &&
          (item.data as { revision?: number; url?: string }).url === event.snapshot.url
      )
      return {
        ...state,
        page: event.page,
        snapshot: event.snapshot,
        evidence: alreadyRecorded
          ? state.evidence
          : addEvidence(state.evidence, {
              kind: 'page',
              source: 'page_state',
              summary: `${event.page.role} ${event.page.items.length} item(s)`,
              confidence: 0.9,
              data: { revision: event.snapshot.revision, url: event.snapshot.url },
            }),
        progress: {
          steps: state.progress.steps + 1,
          lastProgressAt: Date.now(),
          lastProgressKind: 'page',
          replanRequired: false,
        },
      }
    }
    case 'evidence':
      return {
        ...state,
        evidence: addEvidence(state.evidence, event.evidence),
        progress: {
          ...state.progress,
          steps: state.progress.steps + 1,
          lastProgressAt: Date.now(),
          lastProgressKind: event.evidence.kind === 'network' ? 'network' : 'dom',
          replanRequired: false,
        },
      }
    case 'progress':
      return {
        ...state,
        progress: {
          ...state.progress,
          steps: state.progress.steps + 1,
          lastProgressAt: Date.now(),
          lastProgressKind: event.kind,
          replanRequired: event.replanRequired ?? state.progress.replanRequired,
        },
      }
    case 'artifact':
      return {
        ...state,
        artifacts: [...state.artifacts, { path: event.path, kind: event.kind }],
        progress: {
          ...state.progress,
          steps: state.progress.steps + 1,
          lastProgressAt: Date.now(),
          lastProgressKind: 'artifact',
          replanRequired: false,
        },
      }
  }
}
