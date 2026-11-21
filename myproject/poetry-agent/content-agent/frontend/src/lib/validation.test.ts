import { describe, expect, it } from 'vitest';
import { loadActor, ACTOR_STORAGE_KEY, DEFAULT_ACTOR } from './actor';
import { applyDenyReason, canApply, canReview, canReviewSources, reviewDenyReason } from './permissions';
import { rejectGate, verifyGate } from '../pages/sources-page';
import { SOURCES } from '../test/helpers';
import type { Source } from '../api/types';
import { groupEvents, mergeEvents, summarizePayload } from './event-view';
import { parseHash } from './router';
import { validateLocator, validateSignature } from './validation';

describe('署名预检(与后端规则一致)', () => {
  it('必填、长度 2–100', () => {
    expect(validateSignature('')).toMatch(/必填/);
    expect(validateSignature('  ')).toMatch(/必填/);
    expect(validateSignature('李')).toMatch(/2–100/);
    expect(validateSignature('x'.repeat(101))).toMatch(/2–100/);
    expect(validateSignature('李文')).toBeNull();
  });

  it.each(['review-agent', 'My Bot', 'DeerFlow', 'system-admin', 'mcp-user', 'llm-judge', 'ai-reviewer'])(
    '拒绝像 agent 的署名 %s',
    name => {
      expect(validateSignature(name)).toMatch(/不能像 agent/);
    },
  );
});

describe('locator 预检', () => {
  it('拒绝空、占位词和超长', () => {
    expect(validateLocator('')).toMatch(/必填/);
    for (const p of ['空', '待核查', '待人工', '未核对', 'TBD', 'tbd']) expect(validateLocator(p)).toMatch(/占位词/);
    expect(validateLocator('x'.repeat(301))).toMatch(/300/);
  });
  it('“空”只在整体等于占位词时拒绝,不误伤正常文字', () => {
    expect(validateLocator('旧唐书卷九·玄宗纪天空')).toBeNull();
    expect(validateLocator('卷二百一十八')).toBeNull();
  });
});

describe('角色权限', () => {
  it('评审:仅 CONTENT_EDITOR / HISTORICAL_REVIEWER', () => {
    expect(canReview('CONTENT_EDITOR')).toBe(true);
    expect(canReview('HISTORICAL_REVIEWER')).toBe(true);
    expect(canReview('PLATFORM_ADMIN')).toBe(false);
    expect(canReview('RELEASE_MANAGER')).toBe(false);
    expect(reviewDenyReason('RELEASE_MANAGER')).toMatch(/不能评审/);
  });
  it('应用:另含 RELEASE_MANAGER,不含 PLATFORM_ADMIN', () => {
    expect(canApply('RELEASE_MANAGER')).toBe(true);
    expect(canApply('PLATFORM_ADMIN')).toBe(false);
    expect(applyDenyReason('PLATFORM_ADMIN')).toMatch(/不能写入草稿/);
  });
  it('来源核验:仅 HISTORICAL_REVIEWER / PLATFORM_ADMIN', () => {
    expect(canReviewSources('CONTENT_EDITOR')).toBe(false);
    expect(canReviewSources('HISTORICAL_REVIEWER')).toBe(true);
    expect(canReviewSources('PLATFORM_ADMIN')).toBe(true);
  });
});

describe('VERIFY 门槛', () => {
  const [withMissing, allSet] = SOURCES as unknown as Source[];

  it('存在非 SET 的 locator 时禁用并列出缺项', () => {
    const gate = verifyGate('HISTORICAL_REVIEWER', '李文', withMissing!.citations);
    expect(gate.allowed).toBe(false);
    expect(gate.reasons.join('\n')).toContain('claim-a1');
    expect(gate.reasons.join('\n')).not.toContain('claim-a2');
  });

  it('全部 SET、角色与署名合规时允许', () => {
    expect(verifyGate('HISTORICAL_REVIEWER', '李文', allSet!.citations).allowed).toBe(true);
  });

  it('角色不足或署名像 agent 时禁用', () => {
    expect(verifyGate('CONTENT_EDITOR', '李文', allSet!.citations).allowed).toBe(false);
    expect(verifyGate('HISTORICAL_REVIEWER', 'ai-reviewer', allSet!.citations).allowed).toBe(false);
    expect(rejectGate('HISTORICAL_REVIEWER', '').allowed).toBe(false);
    expect(rejectGate('HISTORICAL_REVIEWER', '李文').allowed).toBe(true);
  });
});

describe('actor 存储', () => {
  it('损坏或非法角色回落到默认身份', () => {
    window.localStorage.setItem(ACTOR_STORAGE_KEY, '{oops');
    expect(loadActor()).toEqual(DEFAULT_ACTOR);
    window.localStorage.setItem(ACTOR_STORAGE_KEY, JSON.stringify({ actor_id: 'x', role: 'ROOT' }));
    expect(loadActor()).toEqual(DEFAULT_ACTOR);
  });
});

describe('事件展示', () => {
  it('按类型分组,未知类型进入“其他”', () => {
    const mk = (id: string, t: string) => ({ event_id: id, run_id: 'r', event_type: t, occurred_at: '', payload: {} });
    const groups = groupEvents([mk('1', 'STEP'), mk('2', 'TOOL_CALL'), mk('3', 'RUNTIME_FAILED'), mk('4', 'WEIRD')]);
    expect(groups.map(g => g.group.id)).toEqual(['context', 'model', 'fault', 'other']);
  });

  it('以 event_id 去重并按数字 id 排序', () => {
    const mk = (id: string) => ({ event_id: id, run_id: 'r', event_type: 'STEP', occurred_at: '', payload: {} });
    const merged = mergeEvents([mk('2')], [mk('10'), mk('2'), mk('3')]);
    expect(merged.map(e => e.event_id)).toEqual(['2', '3', '10']);
  });

  it('载荷只展示标量元数据,隐藏疑似正文并折叠对象/数组', () => {
    const summary = summarizePayload({ model: 'm1', ms: 12, prompt: '很长的提示词全文', rules: ['a', 'b'], nested: { x: 1 } });
    expect(summary.text).toContain('model=m1');
    expect(summary.text).toContain('rules=[2 项]');
    expect(summary.text).toContain('nested={…}');
    expect(summary.text).not.toContain('提示词');
    expect(summary.hiddenCount).toBe(1);
  });
});

describe('hash 路由', () => {
  it('解析路径与查询', () => {
    expect(parseHash('#/tasks/task-1?run=run-2')).toEqual({ path: '/tasks/task-1', segments: ['tasks', 'task-1'], query: { run: 'run-2' } });
    expect(parseHash('')).toMatchObject({ path: '/', segments: [] });
  });
});
