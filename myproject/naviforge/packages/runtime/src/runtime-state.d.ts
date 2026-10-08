import type { DomSnapshot } from '@naviforge/dom-plane';
import type { PageState } from './page-state.js';
import { type CapabilityRegistry } from './capability-state.js';
import { addEvidence, type EvidenceStore } from './evidence.js';
import type { TaskContract } from './task-contract.js';
export type ProgressState = {
    steps: number;
    lastProgressAt: number;
    lastProgressKind?: 'page' | 'dom' | 'network' | 'state' | 'artifact' | 'user';
    replanRequired: boolean;
};
export type RuntimeState = {
    task: TaskContract;
    page?: PageState;
    snapshot?: Pick<DomSnapshot, 'revision' | 'url' | 'title'>;
    capabilities: CapabilityRegistry;
    evidence: EvidenceStore;
    progress: ProgressState;
    artifacts: Array<{
        path: string;
        kind?: string;
    }>;
};
export type RuntimeStateEvent = {
    type: 'page_state';
    page: PageState;
    snapshot: Pick<DomSnapshot, 'revision' | 'url' | 'title'>;
} | {
    type: 'evidence';
    evidence: Parameters<typeof addEvidence>[1];
} | {
    type: 'progress';
    kind: ProgressState['lastProgressKind'];
    replanRequired?: boolean;
} | {
    type: 'artifact';
    path: string;
    kind?: string;
};
export declare function createRuntimeState(task: TaskContract, capabilities?: CapabilityRegistry): RuntimeState;
export declare function reduceRuntimeState(state: RuntimeState, event: RuntimeStateEvent): RuntimeState;
