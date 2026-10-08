export type EvidenceKind = 'page' | 'dom' | 'network' | 'tool' | 'user' | 'artifact'

export type Evidence = {
  id: string
  kind: EvidenceKind
  source: string
  summary: string
  at: number
  confidence?: number
  data?: unknown
}

export type EvidenceStore = {
  records: Evidence[]
  nextSeq: number
}

export function createEvidenceStore(): EvidenceStore {
  return { records: [], nextSeq: 1 }
}

export function addEvidence(
  store: EvidenceStore,
  input: Omit<Evidence, 'id' | 'at'> & { at?: number }
): EvidenceStore {
  const evidence: Evidence = {
    ...input,
    id: `${input.kind}-${store.nextSeq}`,
    at: input.at ?? Date.now(),
  }
  return {
    records: [...store.records, evidence],
    nextSeq: store.nextSeq + 1,
  }
}

export function hasEvidenceKind(store: EvidenceStore, source: string): boolean {
  return store.records.some((record) => record.source === source)
}

export function findEvidence(store: EvidenceStore, predicate: (record: Evidence) => boolean): Evidence[] {
  return store.records.filter(predicate)
}
