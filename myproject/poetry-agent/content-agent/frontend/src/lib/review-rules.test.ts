import { describe, expect, it } from 'vitest';
import { DIFF } from '../test/helpers';
import type { DiffChange } from '../api/types';
import {
  buildItemDecisions,
  countApprovedExecutable,
  executableIndexes,
  initialDecisions,
  reviewGate,
  undecidedIndexes,
  type Decisions,
} from './review-rules';

const changes = DIFF.changes as unknown as DiffChange[];
const base = { status: 'REVIEW_REQUIRED', role: 'CONTENT_EDITOR' as const, actorId: 'li-wen', changes };

describe('逐项决定的门槛', () => {
  it('只统计可执行项', () => {
    expect(executableIndexes(changes)).toEqual([0, 1]);
  });

  it('没有逐项决定时,整体批准被挡住并指出缺哪几项', () => {
    const gate = reviewGate({ ...base, action: 'APPROVE', decisions: {} });
    expect(gate.allowed).toBe(false);
    expect(gate.kind).toBe('items');
    expect(gate.reason).toContain('第 0、1 项');
  });

  it('只决定一部分仍然被挡住', () => {
    const decisions: Decisions = { 0: { decision: 'APPROVE', comment: '' } };
    expect(undecidedIndexes(changes, decisions)).toEqual([1]);
    expect(reviewGate({ ...base, action: 'APPROVE', decisions }).allowed).toBe(false);
  });

  it('全部决定后允许整体批准(批准或驳回都算决定)', () => {
    const decisions: Decisions = {
      0: { decision: 'APPROVE', comment: '' },
      1: { decision: 'REJECT', comment: '太泛' },
    };
    expect(reviewGate({ ...base, action: 'APPROVE', decisions }).allowed).toBe(true);
    expect(countApprovedExecutable(changes, decisions)).toBe(1);
  });

  it('整体驳回不要求逐项决定', () => {
    expect(reviewGate({ ...base, action: 'REJECT', decisions: {} }).allowed).toBe(true);
  });

  it('非可执行项不需要决定,没有可执行项时可直接批准', () => {
    const none = changes.filter(c => !c.executable);
    expect(reviewGate({ ...base, changes: none, action: 'APPROVE', decisions: {} }).allowed).toBe(true);
  });

  it('提案已不是待评审时一律挡住', () => {
    const gate = reviewGate({ ...base, status: 'APPROVED', action: 'REJECT', decisions: {} });
    expect(gate).toMatchObject({ allowed: false, kind: 'state' });
  });

  it('角色不在白名单时挡住并说明原因', () => {
    for (const role of ['PLATFORM_ADMIN', 'RELEASE_MANAGER'] as const) {
      const gate = reviewGate({ ...base, role, action: 'REJECT', decisions: {} });
      expect(gate).toMatchObject({ allowed: false, kind: 'role' });
      expect(gate.reason).toContain(role);
    }
    expect(reviewGate({ ...base, role: 'HISTORICAL_REVIEWER', action: 'REJECT', decisions: {} }).allowed).toBe(true);
  });

  it('像 agent 的 actor id 不能评审', () => {
    const gate = reviewGate({ ...base, actorId: 'review-bot', action: 'REJECT', decisions: {} });
    expect(gate).toMatchObject({ allowed: false, kind: 'identity' });
  });
});

describe('item_decisions 组装', () => {
  it('以 change.index 为键,带上评语,跳过未决定的项', () => {
    const decisions: Decisions = {
      1: { decision: 'APPROVE', comment: ' 可用 ' },
      0: { decision: null, comment: '还没想好' },
    };
    expect(buildItemDecisions(changes, decisions)).toEqual([{ item_index: 1, decision: 'APPROVE', comment: '可用' }]);
  });

  it('用服务端已记录的决定初始化', () => {
    const recorded = changes.map(c => (c.index === 0 ? { ...c, item_decision: { decision: 'REJECT' as const, comment: '不准' } } : c));
    expect(initialDecisions(recorded)).toEqual({ 0: { decision: 'REJECT', comment: '不准' } });
  });
});
