import assert from 'node:assert/strict';
import { createTraceRecord } from '@naviforge/session';
import { estimateTokens, promptWouldExceedBudget, projectTraceRecords, } from './working-set.js';
{
    const records = [
        createTraceRecord({ type: 'user.steer', runId: 'working-set', payload: { texts: ['stay'], phase: 'pre_model' } }),
        ...Array.from({ length: 12 }, (_, index) => createTraceRecord({
            type: 'tool.result',
            runId: 'working-set',
            payload: { tool: 'dom_read', arguments: { mode: 'body' }, ok: true, data: { text: 'y'.repeat(8_000) } },
        })),
    ];
    const projection = projectTraceRecords(records, { maxInputTokens: 500 });
    assert.ok(projection.items.some((item) => item.content === 'stay'), 'steering survives record projection');
    assert.ok(!projection.prompt.includes('y'.repeat(500)), 'raw tool payload is not in prompt context');
    assert.ok(projection.estimatedTokens <= 500, 'record projection fits the requested budget');
}
assert.equal(estimateTokens('abcd'), 2);
assert.equal(promptWouldExceedBudget({
    system: 's'.repeat(1_000),
    user: 'u'.repeat(1_000),
    runTotalTokens: 199_000,
    tokenBudget: 200_000,
}), true, 'pre-call budget fires before the next completion');
assert.equal(promptWouldExceedBudget({
    system: 's',
    user: 'u',
    runTotalTokens: 10,
    tokenBudget: 200_000,
}), false, 'small prompts stay under budget');
assert.equal(promptWouldExceedBudget({ system: 's'.repeat(10_000), user: 'u'.repeat(10_000), runTotalTokens: 0, tokenBudget: 0 }), false, 'budget 0 means unlimited');
{
    const records = [
        createTraceRecord({ type: 'run.ask', runId: 'ws', payload: { question: 'Which repo?', wait: 'intake' } }),
        createTraceRecord({ type: 'intake.complete', runId: 'ws', payload: { summary: 'done', roundCount: 1, assumptions: [] } }),
        createTraceRecord({
            type: 'tool.result',
            runId: 'ws',
            payload: {
                tool: 'web_search',
                arguments: { query: 'loopx github' },
                ok: true,
                data: { results: [{ title: 'loopx', url: 'https://github.com/x/loopx', snippet: 'harness' }] },
            },
        }),
    ];
    const projection = projectTraceRecords(records, { maxInputTokens: 4_000 });
    assert.ok(!projection.prompt.includes('Awaiting user:'), 'intake run.ask drops after intake.complete');
    assert.ok(projection.prompt.includes('https://github.com/x/loopx'), 'web_search observation keeps urls');
}
{
    const records = [
        createTraceRecord({
            type: 'run.note',
            runId: 'ws',
            payload: { text: 'GUIDANCE: research: use web_search', topic: 'internal' },
        }),
        createTraceRecord({
            type: 'run.note',
            runId: 'ws',
            payload: { text: 'EVIDENCE: repo A is a harness', topic: 'internal' },
        }),
    ];
    const projection = projectTraceRecords(records, { maxInputTokens: 4_000 });
    assert.ok(projection.prompt.includes('GUIDANCE: research'), 'run.note GUIDANCE projects into CONTEXT');
    assert.ok(projection.prompt.includes('EVIDENCE: repo A'), 'run.note EVIDENCE projects into CONTEXT');
    assert.ok(!projection.prompt.includes('TASK:'), 'task text stays in compileUserPrompt only');
}
{
    const records = [
        createTraceRecord({
            type: 'tool.result',
            runId: 'parent-run',
            payload: { tool: 'dom_read', arguments: {}, ok: true, data: { text: 'parent view' } },
        }),
        createTraceRecord({
            type: 'tool.result',
            runId: 'child-run',
            parentRunId: 'parent-run',
            payload: { tool: 'dom_read', arguments: {}, ok: true, data: { text: 'child spillover' } },
        }),
    ];
    const parentProjection = projectTraceRecords(records, { maxInputTokens: 4_000, ownerRunId: 'parent-run' });
    assert.ok(parentProjection.prompt.includes('parent view'), 'parent projection keeps parent records');
    assert.ok(!parentProjection.prompt.includes('child spillover'), 'parent projection drops child spillover');
    const childProjection = projectTraceRecords(records, { maxInputTokens: 4_000, ownerRunId: 'child-run' });
    assert.ok(childProjection.prompt.includes('child spillover'), 'child projection keeps its own records');
}
console.log('working-set self-check ok');
