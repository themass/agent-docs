import type { DiffChange, ItemDecisionValue, ProposalStatus, ReviewInput, Role } from '../api/types';
import { reviewDenyReason } from './permissions';
import { validateSignature } from './validation';

/** 逐项决定的本地状态,以 change.index 为键(不是数组下标)。 */
export interface LocalDecision {
  decision: ItemDecisionValue | null;
  comment: string;
}
export type Decisions = Record<number, LocalDecision>;

export const executableIndexes = (changes: DiffChange[]): number[] =>
  changes.filter(change => change.executable).map(change => change.index);

/** 还没做决定的可执行项。整体批准的门槛就是这个列表为空。 */
export const undecidedIndexes = (changes: DiffChange[], decisions: Decisions): number[] =>
  executableIndexes(changes).filter(index => !decisions[index]?.decision);

export type GateKind = 'state' | 'role' | 'identity' | 'items';
export interface Gate {
  allowed: boolean;
  reason: string | null;
  kind: GateKind | null;
}

const OPEN: Gate = { allowed: true, reason: null, kind: null };

export interface GateInput {
  action: ItemDecisionValue;
  status: ProposalStatus | string;
  role: Role;
  actorId: string;
  changes: DiffChange[];
  decisions: Decisions;
}

/**
 * 整体评审门槛。判断顺序即提示优先级:状态 → 角色 → 身份 → 逐项。
 * 只有 APPROVE 要求“全部可执行项已逐项决定”;REJECT 不要求。
 * 服务端对同一规则(ITEM_DECISIONS_REQUIRED / REVIEW_ROLE_REQUIRED)再校验一次,以服务端为准。
 */
export function reviewGate(input: GateInput): Gate {
  if (input.status !== 'REVIEW_REQUIRED') {
    return { allowed: false, kind: 'state', reason: `提案已是 ${input.status} 状态,不能再评审。` };
  }
  const roleReason = reviewDenyReason(input.role);
  if (roleReason) return { allowed: false, kind: 'role', reason: roleReason };
  const identity = validateSignature(input.actorId);
  if (identity) {
    return { allowed: false, kind: 'identity', reason: `当前 actor id 不可用于评审:${identity}` };
  }
  if (input.action === 'APPROVE') {
    const missing = undecidedIndexes(input.changes, input.decisions);
    if (missing.length > 0) {
      return {
        allowed: false,
        kind: 'items',
        reason: `还有 ${missing.length} 个可执行项没有逐项决定(第 ${missing.join('、')} 项)。可执行项必须逐项批准或驳回后,才能整体批准。`,
      };
    }
  }
  return OPEN;
}

/** 组装 item_decisions:所有已做决定的项都带上(批准时恰好覆盖全部可执行项)。 */
export function buildItemDecisions(changes: DiffChange[], decisions: Decisions): NonNullable<ReviewInput['item_decisions']> {
  const result: NonNullable<ReviewInput['item_decisions']> = [];
  for (const change of changes) {
    const local = decisions[change.index];
    if (!local?.decision) continue;
    const comment = local.comment.trim();
    result.push({
      item_index: change.index,
      decision: local.decision,
      ...(comment ? { comment } : {}),
    });
  }
  return result;
}

/** 用服务端已记录的逐项决定初始化本地状态。 */
export function initialDecisions(changes: DiffChange[]): Decisions {
  const result: Decisions = {};
  for (const change of changes) {
    if (change.item_decision) {
      result[change.index] = {
        decision: change.item_decision.decision,
        comment: change.item_decision.comment ?? '',
      };
    }
  }
  return result;
}

export function countApprovedExecutable(changes: DiffChange[], decisions: Decisions): number {
  return changes.filter(change => change.executable && decisions[change.index]?.decision === 'APPROVE').length;
}
