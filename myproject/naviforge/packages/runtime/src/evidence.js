export function createEvidenceStore() {
    return { records: [], nextSeq: 1 };
}
export function addEvidence(store, input) {
    const evidence = {
        ...input,
        id: `${input.kind}-${store.nextSeq}`,
        at: input.at ?? Date.now(),
    };
    return {
        records: [...store.records, evidence],
        nextSeq: store.nextSeq + 1,
    };
}
export function hasEvidenceKind(store, source) {
    return store.records.some((record) => record.source === source);
}
export function findEvidence(store, predicate) {
    return store.records.filter(predicate);
}
