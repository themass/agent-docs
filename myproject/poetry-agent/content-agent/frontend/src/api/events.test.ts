import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FakeEventSource } from '../test/helpers';
import { normalizeEvent, openRunEventStream, type StreamState } from './events';
import type { RunEvent } from './types';

function setup(overrides: Partial<Parameters<typeof openRunEventStream>[0]> = {}) {
  const events: RunEvent[] = [];
  const states: StreamState[] = [];
  const poll = vi.fn(async () => undefined);
  const stream = openRunEventStream({
    runId: 'run-1',
    onEvent: e => events.push(e),
    onState: s => states.push(s),
    poll,
    createSource: FakeEventSource.create,
    maxReconnects: 2,
    backoffMs: [100, 200],
    pollIntervalMs: 1000,
    retrySseAfterMs: 5000,
    ...overrides,
  });
  return { stream, events, states, poll };
}

describe('openRunEventStream', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeEventSource.reset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('按事件名分发,并记录最后的事件 id', () => {
    const { stream, events, states } = setup();
    const source = FakeEventSource.last();
    source.open();
    source.emit('STEP', '1', { name: 'load' });
    source.emit('TOOL_CALL', '2', { tool: 'get_snapshot', ms: 12 });
    expect(events.map(e => e.event_type)).toEqual(['STEP', 'TOOL_CALL']);
    expect(stream.lastEventId()).toBe('2');
    expect(states).toEqual(['connecting', 'open']);
  });

  it('浏览器放弃连接后,按退避重建并用 after_event_id 续传', () => {
    const { states } = setup();
    const first = FakeEventSource.last();
    first.open();
    first.emit('STEP', '7');
    first.failFatal();
    expect(states.at(-1)).toBe('reconnecting');
    expect(FakeEventSource.instances).toHaveLength(1);
    vi.advanceTimersByTime(100);
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(new URL(FakeEventSource.last().url).searchParams.get('after_event_id')).toBe('7');
    FakeEventSource.last().open();
    expect(states.at(-1)).toBe('open');
  });

  it('浏览器仍在自动重连时只更新状态,不重复创建连接', () => {
    const { states } = setup();
    FakeEventSource.last().open();
    FakeEventSource.last().failTransient();
    expect(states.at(-1)).toBe('reconnecting');
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it('连续失败超过上限后回退为轮询,并定期尝试恢复 SSE', async () => {
    const { states, poll } = setup();
    FakeEventSource.last().failFatal(); // 第 1 次
    vi.advanceTimersByTime(100);
    FakeEventSource.last().failFatal(); // 第 2 次
    vi.advanceTimersByTime(200);
    FakeEventSource.last().failFatal(); // 第 3 次 > maxReconnects
    expect(states.at(-1)).toBe('polling');
    expect(poll).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(poll).toHaveBeenCalledTimes(2);

    const before = FakeEventSource.instances.length;
    await vi.advanceTimersByTimeAsync(5000);
    expect(FakeEventSource.instances.length).toBe(before + 1);
    FakeEventSource.last().open();
    expect(states.at(-1)).toBe('open');
  });

  it('shouldStop 为真时轮询空转', async () => {
    const { poll } = setup({ maxReconnects: 0, shouldStop: () => true });
    FakeEventSource.last().failFatal();
    await vi.advanceTimersByTimeAsync(3000);
    expect(poll).not.toHaveBeenCalled();
  });

  it('close 之后不再分发事件、不再重连', () => {
    const { stream, events, states } = setup();
    const source = FakeEventSource.last();
    source.open();
    stream.close();
    expect(source.closed).toBe(true);
    expect(states.at(-1)).toBe('closed');
    source.emit('STEP', '9');
    vi.advanceTimersByTime(10000);
    expect(events).toHaveLength(0);
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});

describe('normalizeEvent', () => {
  it('缺 event_id 时使用 lastEventId', () => {
    const msg = new MessageEvent('STEP', { data: JSON.stringify({ payload: { a: 1 } }), lastEventId: '5' });
    expect(normalizeEvent(msg, 'run-1')).toMatchObject({ event_id: '5', event_type: 'STEP', run_id: 'run-1' });
  });

  it('无法解析的数据被丢弃而不是抛错', () => {
    expect(normalizeEvent(new MessageEvent('STEP', { data: 'not json' }), 'run-1')).toBeNull();
    expect(normalizeEvent(new MessageEvent('STEP', { data: '{}' }), 'run-1')).toBeNull();
  });
});

describe('openRunEventStream 的连接票据(登录模式)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeEventSource.reset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const tickets = (...values: string[]) => {
    let i = 0;
    return vi.fn(async () => values[Math.min(i++, values.length - 1)] ?? '');
  };
  const base = (getTicket: () => Promise<string>) => ({
    runId: 'run-1',
    onEvent: () => undefined,
    onState: () => undefined,
    createSource: FakeEventSource.create,
    getTicket,
    maxReconnects: 2,
    backoffMs: [100, 200],
    pollIntervalMs: 1000,
    retrySseAfterMs: 5000,
  });

  it('先取票再连接,票据作为 ticket 查询参数', async () => {
    const getTicket = tickets('tk-1');
    openRunEventStream(base(getTicket));
    expect(FakeEventSource.instances).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(0);
    expect(getTicket).toHaveBeenCalledTimes(1);
    expect(new URL(FakeEventSource.last().url).searchParams.get('ticket')).toBe('tk-1');
  });

  it('断线后每次重连都重新取票,并带 after_event_id', async () => {
    const getTicket = tickets('tk-1', 'tk-2');
    openRunEventStream(base(getTicket));
    await vi.advanceTimersByTimeAsync(0);
    const first = FakeEventSource.last();
    first.open();
    first.emit('STEP', '12');
    first.failFatal();
    await vi.advanceTimersByTimeAsync(100);
    expect(getTicket).toHaveBeenCalledTimes(2);
    const params = new URL(FakeEventSource.last().url).searchParams;
    expect(params.get('ticket')).toBe('tk-2');
    expect(params.get('after_event_id')).toBe('12');
  });

  it('带票据的连接即使浏览器还在自动重连也改为手动重建(旧票据已过期)', async () => {
    const getTicket = tickets('tk-1', 'tk-2');
    openRunEventStream(base(getTicket));
    await vi.advanceTimersByTimeAsync(0);
    FakeEventSource.last().open();
    FakeEventSource.last().failTransient();
    expect(FakeEventSource.last().closed).toBe(true);
    await vi.advanceTimersByTimeAsync(100);
    expect(getTicket).toHaveBeenCalledTimes(2);
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it('离线演示模式返回空票据:不加 ticket 参数', async () => {
    openRunEventStream(base(tickets('')));
    await vi.advanceTimersByTimeAsync(0);
    expect(new URL(FakeEventSource.last().url).searchParams.has('ticket')).toBe(false);
  });

  it('取票失败按连接失败处理,超过上限后回退轮询', async () => {
    const states: StreamState[] = [];
    const poll = vi.fn(async () => undefined);
    const getTicket = vi.fn(async () => {
      throw new Error('ticket failed');
    });
    openRunEventStream({ ...base(getTicket), onState: s => states.push(s), poll });
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(100);
    await vi.advanceTimersByTimeAsync(200);
    expect(states.at(-1)).toBe('polling');
    expect(poll).toHaveBeenCalled();
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it('取票期间关闭流:不会再创建连接', async () => {
    const stream = openRunEventStream(base(tickets('tk-1')));
    stream.close();
    await vi.advanceTimersByTimeAsync(0);
    expect(FakeEventSource.instances).toHaveLength(0);
  });
});
