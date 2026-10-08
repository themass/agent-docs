import assert from 'node:assert/strict';
import { Agent, AgentCtx } from './agent-ctx.js';
import { createRunHooks, SkillAllowlistHook, TaskHintHook, ToolStateHook } from './builtin-hooks.js';
import { HookPipeline, ProtocolHook, ToolOutcomeHook, WorkingSetHook } from './hooks.js';
import { ToolOutcomePolicy } from './failure.js';
const record = (id, type, payload) => ({
    schema: 1,
    id,
    at: 1,
    runId: 'run-1',
    channel: type === 'user.steer' ? 'conversation' : 'trace',
    type,
    payload,
});
const snap = {
    revision: 1,
    url: 'https://example.test/page',
    title: 't',
    header: '',
    content: '',
    footer: '',
};
function testAgent(over = {}) {
    return new Agent({
        task: 't',
        llm: { baseURL: 'http://x', apiKey: 'x', model: 'x' },
        dom: { snapshot: async () => ({ ok: true, data: snap }) },
        ...over,
    });
}
{
    const { pipeline, protocol } = createRunHooks(2);
    const ctx = new AgentCtx(testAgent({}), snap);
    ctx.ledger.append(record('steer-1', 'user.steer', { texts: ['stay'], phase: 'pre_model' }));
    const prepared = await pipeline.beforeModel(ctx);
    assert.equal(prepared.kind, 'continue');
    assert.ok(ctx.prompt.user.includes('CONSTRAINT: stay'));
    assert.ok(ctx.tools.length > 0, 'beforeModel syncs tools onto ctx');
    ctx.completion = { content: '### 一句话\n这是项目介绍。\n### 适合谁\n开发者' };
    const invalid = pipeline.afterModel(ctx);
    assert.equal(invalid.kind, 'retry_turn');
    ctx.completion = { content: 'not a turn' };
    const stopped = pipeline.afterModel(ctx);
    assert.equal(stopped.kind, 'stop');
    protocol.reset();
}
{
    // Regression for tests/message.txt: a safety/policy refusal with no tool
    // call must stop immediately as `blocked`, not after burning the full
    // protocol retry budget as a generic `error`. Retrying "you must call a
    // tool" against a refusal just reproduces the same refusal.
    const { pipeline, protocol } = createRunHooks(2);
    const ctx = new AgentCtx(testAgent({}), snap);
    const prepared = await pipeline.beforeModel(ctx);
    assert.equal(prepared.kind, 'continue');
    ctx.completion = {
        content: "I can't help retrieve or extract playback links for sexually exploitative content, including material involving alleged rape or minors.",
    };
    const refused = pipeline.afterModel(ctx);
    assert.equal(refused.kind, 'stop', 'first safety refusal must stop immediately, not retry_turn');
    if (refused.kind === 'stop') {
        assert.equal(refused.status, 'blocked');
    }
    protocol.reset();
}
{
    // A Chinese-language refusal must be recognized too — this is a generic
    // lexical pattern, not an English-only heuristic.
    const { pipeline, protocol } = createRunHooks(2);
    const ctx = new AgentCtx(testAgent({}), snap);
    await pipeline.beforeModel(ctx);
    ctx.completion = { content: '我无法协助获取涉及未成年人的色情内容的播放链接。' };
    const refused = pipeline.afterModel(ctx);
    assert.equal(refused.kind, 'stop', 'zh safety refusal must also stop immediately');
    if (refused.kind === 'stop') {
        assert.equal(refused.status, 'blocked');
    }
    protocol.reset();
}
{
    const tools = new ToolOutcomeHook(new ToolOutcomePolicy(1));
    const pipeline = new HookPipeline([
        new WorkingSetHook(),
        new ProtocolHook(),
        tools,
        {
            name: 'empty-notes',
            afterTool() {
                return { notes: [] };
            },
        },
    ]);
    const ctx = new AgentCtx(testAgent({}), snap);
    ctx.toolCall = { tool: 'dom_execute_js', arguments: {} };
    ctx.toolResult = { ok: false, error: { code: 'execute_js_denied', message: 'off', recoverable: false } };
    const denied = pipeline.afterTool(ctx);
    assert.ok(denied.forceAsk, 'later afterTool notes must not drop forceAsk');
}
{
    const ctx = new AgentCtx(testAgent({}), snap);
    ctx.ledger.append(record('steer-2', 'user.steer', { texts: ['stay'], phase: 'pre_model' }));
    assert.equal(ctx.compileUser().includes('USER CORRECTION'), false, 'compileUser ignores ledger until projected');
    const prepared = await ctx.agent.hooks.beforeModel(ctx);
    assert.equal(prepared.kind, 'continue');
    assert.ok(ctx.compileUser().includes('CONSTRAINT: stay'), 'after beforeModel, messages are the compile source');
}
{
    const ctx = new AgentCtx(testAgent({ maxInputTokens: 50 }), snap);
    for (let i = 0; i < 10; i += 1) {
        ctx.ledger.append(record(`tool-${i}`, 'tool.result', {
            tool: 'dom_read',
            arguments: { mode: 'list' },
            ok: true,
            data: { items: Array(400).fill('item') },
        }));
    }
    const result = await ctx.agent.hooks.beforeModel(ctx);
    assert.equal(result.kind, 'stop', 'input cap stops before the LLM call');
}
{
    let calls = 0;
    const ctx = new AgentCtx(testAgent({
        maxInputTokens: 200,
        contextCompactor: {
            compact: async (input) => {
                calls += 1;
                return {
                    summary: 'Compacted audit history.',
                    preservedConstraints: input.constraints,
                    openWork: input.openWork,
                    tokenUsage: 7,
                };
            },
        },
    }), snap);
    for (let i = 0; i < 10; i += 1) {
        ctx.ledger.append(record(`pressure-${i}`, 'tool.result', { tool: 'dom_read', arguments: { mode: 'body' }, ok: true, data: { text: 'x'.repeat(500) } }));
    }
    await ctx.agent.hooks.beforeModel(ctx);
    assert.equal(calls, 1, 'L2 invokes once when L1 cannot fit the input cap');
    assert.ok(ctx.ledger.all().some((entry) => entry.type === 'context.compaction'), 'compaction is retained in the ledger');
    assert.ok(ctx.ledger.all().some((entry) => entry.type === 'run.recovery'), 'compaction emits fold_context recovery');
    assert.ok(ctx.ledger.all().some((entry) => entry.type === 'metrics.context'), 'compaction emits context metrics');
}
{
    const ctx = new AgentCtx(testAgent({
        maxInputTokens: 200,
        contextCompactor: { compact: async () => { throw new Error('unavailable'); } },
    }), snap);
    const before = ctx.ledger.all().length;
    for (let i = 0; i < 10; i += 1) {
        ctx.ledger.append(record(`failure-${i}`, 'tool.result', { tool: 'dom_read', arguments: { mode: 'body' }, ok: true, data: { text: 'x'.repeat(500) } }));
    }
    await ctx.agent.hooks.beforeModel(ctx);
    assert.equal(ctx.ledger.all().filter((entry) => entry.type !== 'metrics.context').length, before + 10, 'L2 failure leaves every audit record intact');
    assert.ok(ctx.prompt.user.includes('CONTEXT'), 'L2 failure uses deterministic L1 fallback');
}
{
    const ctx = new AgentCtx(testAgent({ allowedTools: ['dom_click'] }), snap);
    ctx.toolCall = { tool: 'network_intercept', arguments: { rules: [] } };
    const gate = new SkillAllowlistHook().beforeTool(ctx);
    assert.equal(gate.kind, 'skip_tool');
    if (gate.kind === 'skip_tool')
        assert.equal(gate.privacy?.code, 'skill_allowlist');
}
{
    const agent = testAgent({
        hooks: [
            {
                name: 'rewrite-bundle',
                beforeModel(ctx) {
                    ctx.prompt.user = `${ctx.prompt.user}\n#plugin extra`;
                    ctx.tools = ctx.tools.filter((tool) => tool.function.name !== 'dom_execute_js');
                    ctx.skills = ctx.skills.filter((skill) => skill.id !== 'gone');
                    return { kind: 'continue' };
                },
            },
        ],
    });
    const ctx = new AgentCtx(agent, snap);
    ctx.skills.push({ id: 'gone', version: '1', description: 'x', instructions: 'x' });
    const prepared = await agent.hooks.beforeModel(ctx);
    assert.equal(prepared.kind, 'continue');
    assert.ok(ctx.prompt.user.includes('#plugin extra'), 'extra hook may rewrite the user prompt');
    assert.ok(!ctx.tools.some((tool) => tool.function.name === 'dom_execute_js'), 'extra hook may drop a tool from the model bundle');
    assert.ok(!ctx.skills.some((skill) => skill.id === 'gone'), 'extra hook may rewrite skills');
}
{
    const agent = testAgent({});
    agent.skills.push({ id: 'kept', version: '1', description: 'x', instructions: 'x' });
    const ctx = new AgentCtx(agent, snap);
    ctx.skills = [];
    const prepared = await agent.hooks.beforeModel(ctx);
    assert.equal(prepared.kind, 'continue');
    assert.ok(ctx.skills.some((skill) => skill.id === 'kept'), 'beforeModel recopies skills from the Agent bag');
}
{
    const read = new AgentCtx(testAgent({ task: '详细介绍一下这个项目' }), snap);
    read.gates.deliverable = 'summary';
    new TaskHintHook().beforeStep(read);
    assert.ok(![...read.ledger.all()].some((entry) => entry.type === 'run.note' && entry.payload.text.startsWith('GUIDANCE:')), 'locked summary deliverable skips TaskHint GUIDANCE (PLAN lives in preflight)');
    const n = read.ledger.all().length;
    new TaskHintHook().beforeStep(read);
    assert.equal(read.ledger.all().length, n, 'the hint gate is issued once per task');
    const mark = new AgentCtx(testAgent({ task: '标记当前页面 top5 视频' }), snap);
    new TaskHintHook().beforeStep(mark);
    assert.ok(![...mark.ledger.all()].some((entry) => entry.type === 'run.note' && entry.payload.text.startsWith('GUIDANCE:')), 'marking tasks skip the steering hint');
}
{
    const ctx = new AgentCtx(testAgent({}), snap);
    ctx.toolCall = { tool: 'skill_load', arguments: { id: 'list-then-detail' } };
    ctx.toolResult = {
        ok: true,
        data: { id: 'list-then-detail', body: 'do extract then click' },
    };
    ctx.toolTrace = 'skill_load ok';
    new ToolStateHook().afterTool(ctx);
    assert.ok(ctx.gates.loadedSkillIds.has('list-then-detail'));
    assert.equal(ctx.gates.loadedSkillBodies[0], 'do extract then click');
    ctx.toolCall = { tool: 'dom_read', arguments: { mode: 'list', n: 3 } };
    ctx.toolResult = {
        ok: true,
        data: { items: [{ index: 1, title: 'A', url: 'https://x.example/a' }] },
    };
    ctx.toolTrace = 'extract ok';
    new ToolStateHook().afterTool(ctx);
    assert.equal(ctx.gates.lastListHints[0]?.title, 'A');
    assert.ok(ctx.gates.seenObs.has(`dom_read|${snap.url}|list`));
}
console.log('hooks.self-check ok');
