import type { ToolResult } from '@naviforge/shared'

import type { Deliverable } from './deliverable.js'
import type { Evidence } from './evidence.js'
import { evaluateEvidence, type EvaluationResult } from './evaluator.js'
import type { RecoveryPlan } from './recovery.js'
import type { TaskContract } from './task-contract.js'

/** Outcome of a system_done attempt — owned by the completion coordinator, not hooks. */
export type CompletionDecision =
  | { allow: true }
  | {
      allow: false
      code: string
      message: string
      note: string
      recovery: RecoveryPlan
    }

export type CompletionInput = {
  deliverable: Deliverable
  taskContract: TaskContract
  evidence: readonly Evidence[]
  scriptSaved: boolean
  subtaskEvidenceReady: boolean
  systemDoneResult: string
}

/**
 * Decide whether system_done may complete. Callers (DeliverableVerifyHook) only
 * translate this into a HookDecision — business completion lives here.
 */
export function evaluateCompletion(input: CompletionInput): CompletionDecision {
  const result = input.systemDoneResult

  if (input.deliverable === 'script' && !input.scriptSaved) {
    const hasPath = /scripts?\//i.test(result) || /\.py\b/i.test(result)
    if (!hasPath) {
      return {
        allow: false,
        code: 'deliverable_verify',
        message: 'script deliverable requires script_save before system_done',
        note:
          'CONSTRAINT: deliverable=script 须先 script_save 成功，再 system_done 附 path。若缺 URL/登录/Network，用 shortfall 模板说明，禁止空完成。',
        recovery: {
          strategy: 'reobserve_and_replan',
          retryable: true,
          diagnostic: 'script_save missing before system_done',
        },
      }
    }
  }

  if (input.deliverable === 'media') {
    const hasUrl = /https?:\/\//i.test(result) && /m3u8|mp4|webm|media/i.test(result)
    const hasShortfall = /shortfall|无法|unavailable|缺少|未能|未找到|无.*源/i.test(result)
    const sourceRequired = input.taskContract.capabilities.network === 'required'
    const evaluation = evaluateEvidence(input.taskContract, input.evidence)
    const verifiedSource =
      evaluation.status === 'complete' ||
      input.evidence.some((item) => item.kind === 'network' && item.source === 'network_media')

    if (sourceRequired && !verifiedSource && !hasShortfall) {
      return {
        allow: false,
        code: 'deliverable_verify',
        message: 'strict media task requires network_media evidence or explicit shortfall',
        note:
          'CONSTRAINT: media source evidence is missing — model text alone cannot verify an original playback URL. Retry candidate click + Network, or return an explicit shortfall.',
        recovery: coordinateRecovery({
          evaluation,
          replanRequired: true,
          networkRequired: true,
          networkUnavailable: false,
        }) ?? {
          strategy: 'reobserve_and_replan',
          retryable: true,
          diagnostic: 'missing network_media evidence',
        },
      }
    }

    if (!sourceRequired && !hasUrl && !hasShortfall && !input.subtaskEvidenceReady) {
      return {
        allow: false,
        code: 'deliverable_verify',
        message: 'media deliverable needs mediaUrl, spawn evidence, or explicit shortfall',
        note:
          'CONSTRAINT: deliverable=media — system_done 须含 mediaUrl（m3u8/mp4 等）或明确 shortfall；若仅拿到标题可先 click+network，或 script_save 骨架。',
        recovery: {
          strategy: 'reobserve_and_replan',
          retryable: true,
          diagnostic: 'vague media system_done',
        },
      }
    }
  }

  return { allow: true }
}

export type RecoveryCoordinateInput = {
  evaluation: EvaluationResult
  replanRequired: boolean
  networkRequired: boolean
  networkUnavailable: boolean
}

/**
 * Map runtime signals (evidence gap / replan / capability loss) to a RecoveryPlan.
 * Hooks and loop guards consume this instead of inventing ad-hoc stop text.
 */
export function coordinateRecovery(input: RecoveryCoordinateInput): RecoveryPlan | null {
  if (input.networkRequired && input.networkUnavailable) {
    return {
      strategy: 'ask_user',
      retryable: true,
      diagnostic: NETWORK_COLLABORATION_QUESTION,
    }
  }
  if (input.evaluation.status === 'blocked') {
    return {
      strategy: 'stop',
      retryable: false,
      diagnostic: input.evaluation.reason ?? 'evaluation blocked',
    }
  }
  if (input.evaluation.status === 'needs_recovery') {
    return {
      strategy: input.replanRequired ? 'reobserve_and_replan' : 'reobserve_and_replan',
      retryable: true,
      diagnostic: input.evaluation.reason ?? `missing: ${input.evaluation.missing.join(', ')}`,
    }
  }
  if (input.replanRequired) {
    return {
      strategy: 'reobserve_and_replan',
      retryable: true,
      diagnostic: 'replanRequired — change tool or evidence surface',
    }
  }
  return null
}

/** Standardized user collaboration copy when Network is required but unavailable. */
export const NETWORK_COLLABORATION_QUESTION =
  'Network 能力当前不可用（可能被 DevTools 或其他扩展占用 debugger）。请关闭冲突后回复「重试」，或提供已打开的播放页链接；也可回复 shortfall 结束。'

export function needsNetworkCollaboration(input: {
  networkRequired: boolean
  networkUnavailable: boolean
}): boolean {
  return input.networkRequired && input.networkUnavailable
}

export function completionToToolResult(decision: Extract<CompletionDecision, { allow: false }>): ToolResult {
  return {
    ok: false,
    error: {
      code: decision.code,
      message: decision.message,
      recoverable: decision.recovery.retryable,
    },
  }
}
