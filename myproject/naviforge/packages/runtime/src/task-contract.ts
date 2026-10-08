import { resolveTaskScope, type TaskScope } from '@naviforge/policy'

import { resolveDeliverable, type Deliverable } from './deliverable.js'
import { resolveTaskIntent, type TaskIntent } from './task-intent.js'

export type TaskEvidenceRequirement =
  | 'page_state'
  | 'page_content'
  | 'list_items'
  | 'detail_page'
  | 'comparison_sources'
  | 'artifact'
  | 'title'
  | 'page_url'
  | 'media_url'
  | 'network_provenance'

export type TaskCapabilityRequirement = 'dom' | 'tabs' | 'network' | 'search' | 'fetch' | 'workspace' | 'hitl'

export type TaskContract = {
  version: 1
  task: string
  intent: TaskIntent
  deliverable: Deliverable
  scope: TaskScope
  requiredEvidence: TaskEvidenceRequirement[]
  capabilities: Partial<Record<TaskCapabilityRequirement, 'required' | 'preferred' | 'not_needed'>>
  completion: 'strict' | 'partial_allowed'
  allowedFallbacks: string[]
  maxRecoveryAttempts: number
}

const MEDIA_SOURCE_REQUEST = /原地址|源地址|播放源|播放地址|播放链接|视频链接|源链接|直链|直达链接|media\s*url|stream\s*url|media\s*link|stream\s*link|m3u8|mp4|hls|webm/i
const EXTERNAL_WRITE_REQUEST = /提交|发布|发送|付款|支付|删除|上传|购买|下单|send|submit|publish|pay|delete|upload|purchase/i

function unique<T>(items: T[]): T[] {
  return [...new Set(items)]
}

/**
 * Build the generic task contract used by Planner/Policy/Evaluator layers.
 * This is intentionally domain-neutral: media fields are one deliverable
 * contract, not a media-specific Runtime mode.
 */
export function buildTaskContract(task: string): TaskContract {
  const normalized = task.trim()
  const intent = resolveTaskIntent(normalized)
  const deliverable = resolveDeliverable(normalized)
  const sourceRequired = deliverable === 'media' && MEDIA_SOURCE_REQUEST.test(normalized)

  let requiredEvidence: TaskEvidenceRequirement[]
  switch (deliverable) {
    case 'media':
      requiredEvidence = sourceRequired
        ? ['page_state', 'title', 'media_url', 'network_provenance']
        : ['page_state', 'title']
      break
    case 'data':
      requiredEvidence = ['page_state', 'list_items']
      break
    case 'research':
      requiredEvidence = ['comparison_sources']
      break
    case 'script':
      requiredEvidence = ['page_state', 'artifact']
      break
    case 'summary':
      requiredEvidence = ['page_content']
      break
    default:
      requiredEvidence = ['page_state']
  }

  const network: 'required' | 'preferred' | 'not_needed' =
    deliverable === 'media' && sourceRequired
      ? 'required'
      : deliverable === 'media' || deliverable === 'research'
        ? 'preferred'
        : 'not_needed'

  const capabilities: TaskContract['capabilities'] = {
    dom: 'required',
    tabs: intent === 'multi_hop_crawl' || intent === 'list_detail' || intent === 'research' ? 'preferred' : 'not_needed',
    network,
    search: intent === 'research' ? 'required' : 'not_needed',
    fetch: intent === 'research' || intent === 'multi_hop_crawl' ? 'preferred' : 'not_needed',
    workspace: deliverable === 'script' ? 'required' : deliverable === 'data' ? 'preferred' : 'not_needed',
    hitl: EXTERNAL_WRITE_REQUEST.test(normalized) ? 'required' : 'preferred',
  }

  return {
    version: 1,
    task: normalized,
    intent,
    deliverable,
    scope: resolveTaskScope(normalized),
    requiredEvidence: unique(requiredEvidence),
    capabilities,
    completion: sourceRequired || deliverable === 'script' ? 'strict' : 'partial_allowed',
    allowedFallbacks:
      deliverable === 'media'
        ? ['title_and_page_url_with_explicit_shortfall']
        : deliverable === 'script'
          ? ['structured_shortfall_without_claiming_script_created']
          : ['explicit_shortfall_with_attempted_steps'],
    maxRecoveryAttempts: deliverable === 'media' ? 3 : 2,
  }
}

export function requiresTaskEvidence(contract: TaskContract, requirement: TaskEvidenceRequirement): boolean {
  return contract.requiredEvidence.includes(requirement)
}

export function taskContractSummary(contract: TaskContract): string {
  return [
    `intent=${contract.intent}`,
    `deliverable=${contract.deliverable}`,
    `completion=${contract.completion}`,
    `requiredEvidence=${contract.requiredEvidence.join(',')}`,
    `network=${contract.capabilities.network ?? 'not_needed'}`,
  ].join(' ')
}
