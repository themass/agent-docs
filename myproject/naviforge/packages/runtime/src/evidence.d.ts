export type EvidenceKind = 'page' | 'dom' | 'network' | 'tool' | 'user' | 'artifact';
export type Evidence = {
    id: string;
    kind: EvidenceKind;
    source: string;
    summary: string;
    at: number;
    confidence?: number;
    data?: unknown;
};
export type EvidenceStore = {
    records: Evidence[];
    nextSeq: number;
};
export declare function createEvidenceStore(): EvidenceStore;
export declare function addEvidence(store: EvidenceStore, input: Omit<Evidence, 'id' | 'at'> & {
    at?: number;
}): EvidenceStore;
export declare function hasEvidenceKind(store: EvidenceStore, source: string): boolean;
export declare function findEvidence(store: EvidenceStore, predicate: (record: Evidence) => boolean): Evidence[];
