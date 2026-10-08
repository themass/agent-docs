import type { TaskEvidenceRequirement, TaskContract } from './task-contract.js';
import type { Evidence } from './evidence.js';
export type EvaluationStatus = 'complete' | 'partial' | 'needs_recovery' | 'blocked';
export type EvaluationResult = {
    status: EvaluationStatus;
    missing: TaskEvidenceRequirement[];
    evidence: Evidence[];
    reason?: string;
};
export declare function evaluateEvidence(contract: TaskContract, evidence: readonly Evidence[]): EvaluationResult;
