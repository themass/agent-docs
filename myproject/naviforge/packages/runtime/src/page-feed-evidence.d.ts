import type { DomSnapshot } from '@naviforge/dom-plane';
/** Titles / labels visible in snapshot text but missing from structured extract (SPA feeds). */
export declare function extractFeedLabelsFromSnapshot(snap: DomSnapshot, limit?: number): string[];
export declare function formatFeedEvidenceNote(labels: string[]): string;
