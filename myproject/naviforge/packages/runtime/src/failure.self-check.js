import assert from 'node:assert/strict';
import { Agent, AgentCtx } from './agent-ctx.js';
import { interpretTurn, looksLikeSafetyRefusal, ToolOutcomePolicy } from './failure.js';
import { ProtocolHook } from './hooks.js';
{
    const command = interpretTurn({
        content: 'click it',
        toolCalls: [{ name: 'dom_click', arguments: { index: 1 } }],
    });
    assert.equal(command.kind, 'proceed');
    if (command.kind === 'proceed')
        assert.equal(command.decision.call.tool, 'dom_click');
}
{
    const command = interpretTurn({
        content: '### 一句话\nNaviForge 是浏览器 Agent。\n### 适合谁\n本地用户',
    });
    assert.equal(command.kind, 'retry_turn', 'Markdown cannot be salvaged into system_done');
}
{
    const command = interpretTurn({
        content: '',
        toolCalls: [
            { name: 'dom_click', arguments: { index: 1 } },
            { name: 'system_done', arguments: { result: 'ignored' } },
        ],
    });
    assert.equal(command.kind, 'retry_turn', 'mixed multiple function calls retry with guidance');
}
{
    const command = interpretTurn({
        content: 'batch fetch',
        toolCalls: [
            { name: 'fetch_text', arguments: { url: 'https://raw.githubusercontent.com/o/r/a.md' } },
            { name: 'fetch_text', arguments: { url: 'https://raw.githubusercontent.com/o/r/b.md' } },
            { name: 'fetch_text', arguments: { url: 'https://raw.githubusercontent.com/o/r/c.md' } },
            { name: 'fetch_text', arguments: { url: 'https://raw.githubusercontent.com/o/r/d.md' } },
            { name: 'fetch_text', arguments: { url: 'https://raw.githubusercontent.com/o/r/e.md' } },
        ],
    });
    assert.equal(command.kind, 'proceed', 'five parallel fetch_text calls coalesce');
    if (command.kind === 'proceed') {
        assert.equal(command.decision.call.arguments.urls.length, 5);
    }
}
{
    const command = interpretTurn({ content: '### not json and not a full writeup' });
    assert.equal(command.kind, 'retry_turn');
    if (command.kind === 'retry_turn') {
        assert.equal(command.plan.strategy, 'protocol_retry');
        assert.ok(command.hint.startsWith('GUIDANCE:'));
    }
}
{
    const snap = {
        revision: 1,
        url: 'https://example.test/page',
        title: 't',
        header: '',
        content: '',
        footer: '',
    };
    const ctx = new AgentCtx(new Agent({
        task: 't',
        llm: { baseURL: 'http://x', apiKey: 'x', model: 'x' },
        dom: { snapshot: async () => ({ ok: true, data: snap }) },
    }), snap);
    const protocol = new ProtocolHook();
    ctx.completion = { content: 'nope' };
    const first = protocol.afterModel(ctx);
    ctx.completion = { content: 'still nope' };
    const second = protocol.afterModel(ctx);
    assert.equal(first.kind, 'retry_turn');
    assert.equal(second.kind, 'stop', 'the second invalid completion terminates without HITL');
}
{
    const policy = new ToolOutcomePolicy(2);
    const once = policy.onFailure({
        tool: 'dom_click',
        code: 'selector',
        message: 'miss',
        listHints: [],
    });
    assert.equal(once.forceAsk, undefined);
    const twice = policy.onFailure({
        tool: 'dom_click',
        code: 'selector',
        message: 'miss',
        listHints: [],
    });
    assert.ok(twice.forceAsk?.includes('failed 2 times'));
}
{
    const policy = new ToolOutcomePolicy(2);
    const denied = policy.onFailure({
        tool: 'dom_execute_js',
        code: 'execute_js_denied',
        message: 'off',
        listHints: [],
    });
    assert.ok(denied.forceAsk?.includes('blocked by settings'));
}
{
    const policy = new ToolOutcomePolicy(2);
    const nav = policy.onFailure({
        tool: 'dom_navigate',
        code: 'bad_args',
        message: 'empty',
        listHints: [{ index: 1, title: 'A', url: 'https://a.example' }],
    });
    assert.ok(nav.notes.some((line) => line.includes('FORBIDDEN empty dom_navigate')));
    assert.ok(nav.notes.some((line) => line.includes('index=1')));
}
// looksLikeSafetyRefusal — generic lexical classifier, not a per-site rule.
assert.equal(looksLikeSafetyRefusal("I can't help retrieve or extract playback links for sexually exploitative content, including material involving alleged rape or minors."), true);
assert.equal(looksLikeSafetyRefusal('我无法协助获取涉及未成年人色情内容的播放链接。'), true);
assert.equal(looksLikeSafetyRefusal('这违反了使用政策，我不予提供。'), true);
// Ordinary protocol confusion / markdown output must NOT be misclassified as
// a safety refusal — those should still go through the normal retry budget.
assert.equal(looksLikeSafetyRefusal('### 一句话\nNaviForge 是浏览器 Agent。'), false);
assert.equal(looksLikeSafetyRefusal('not a turn'), false);
assert.equal(looksLikeSafetyRefusal(''), false);
console.log('failure.self-check ok');
