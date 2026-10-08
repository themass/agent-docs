import type { TaskEvidenceRequirement, TaskContract } from './task-contract.js'
import type { Evidence } from './evidence.js'

export type EvaluationStatus = 'complete' | 'partial' | 'needs_recovery' | 'blocked'

export type EvaluationResult = {
  status: EvaluationStatus
  missing: TaskEvidenceRequirement[]
  evidence: Evidence[]
  reason?: string
}

export function evaluateEvidence(contract: TaskContract, evidence: readonly Evidence[]): EvaluationResult {
  const present = new Set<TaskEvidenceRequirement>()
  for (const item of evidence) {
    if (item.kind === 'page') present.add('page_state')
    if (item.kind === 'dom') present.add('page_content')
    if (item.kind === 'network') {
      present.add('media_url')
      present.add('network_provenance')
    }
    if (item.source === 'media_title') present.add('title')
    if (item.source === 'page_url') present.add('page_url')
    if (item.source === 'list_items') present.add('list_items')
    if (item.source === 'artifact') present.add('artifact')
    if (item.source === 'comparison_source') present.add('comparison_sources')
    if (item.source === 'detail_page') present.add('detail_page')
  }

  const missing = contract.requiredEvidence.filter((requirement) => !present.has(requirement))
  if (!missing.length) return { status: 'complete', missing, evidence: [...evidence] }
  if (contract.completion === 'partial_allowed') {
    return { status: 'partial', missing, evidence: [...evidence], reason: 'partial evidence is allowed by task contract' }
  }
  return { status: 'needs_recovery', missing, evidence: [...evidence], reason: 'required evidence is missing' }
}
