import { createCapabilityRegistry } from './capability-state.js';
import { createEvidenceStore, addEvidence } from './evidence.js';
export function createRuntimeState(task, capabilities) {
    return {
        task,
        capabilities: capabilities ?? createCapabilityRegistry(),
        evidence: createEvidenceStore(),
        progress: { steps: 0, lastProgressAt: Date.now(), replanRequired: false },
        artifacts: [],
    };
}
export function reduceRuntimeState(state, event) {
    switch (event.type) {
        case 'page_state': {
            const alreadyRecorded = state.evidence.records.some((item) => item.source === 'page_state' &&
                typeof item.data === 'object' &&
                item.data !== null &&
                item.data.revision === event.snapshot.revision &&
                item.data.url === event.snapshot.url);
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
            };
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
            };
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
            };
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
            };
    }
}
