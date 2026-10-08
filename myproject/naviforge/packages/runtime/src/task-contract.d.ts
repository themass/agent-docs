import { type TaskScope } from '@naviforge/policy';
import { type Deliverable } from './deliverable.js';
import { type TaskIntent } from './task-intent.js';
export type TaskEvidenceRequirement = 'page_state' | 'page_content' | 'list_items' | 'detail_page' | 'comparison_sources' | 'artifact' | 'title' | 'page_url' | 'media_url' | 'network_provenance';
export type TaskCapabilityRequirement = 'dom' | 'tabs' | 'network' | 'search' | 'fetch' | 'workspace' | 'hitl';
export type TaskContract = {
    version: 1;
    task: string;
    intent: TaskIntent;
    deliverable: Deliverable;
    scope: TaskScope;
    requiredEvidence: TaskEvidenceRequirement[];
    capabilities: Partial<Record<TaskCapabilityRequirement, 'required' | 'preferred' | 'not_needed'>>;
    completion: 'strict' | 'partial_allowed';
    allowedFallbacks: string[];
    maxRecoveryAttempts: number;
};
/**
 * Build the generic task contract used by Planner/Policy/Evaluator layers.
 * This is intentionally domain-neutral: media fields are one deliverable
 * contract, not a media-specific Runtime mode.
 */
export declare function buildTaskContract(task: string): TaskContract;
export declare function requiresTaskEvidence(contract: TaskContract, requirement: TaskEvidenceRequirement): boolean;
export declare function taskContractSummary(contract: TaskContract): string;
