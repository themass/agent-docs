import { runEventsUrl } from './client';
import type { RunEvent } from './types';
import { isRecord, str } from '../lib/guards';

/** 契约 §7.1 的事件类型;SSE 的 event 名 = event_type,必须逐个注册监听。 */
export const EVENT_TYPES = [
  'RUN_CREATED',
  'RUNTIME_ADMISSION',
  'RUN_STATE_CHANGED',
  'RUN_STARTED',
  'CONTEXT_LOADED',
  'STEP',
  'TOOL_CALL',
  'MODEL_USAGE',
  'BUDGET_UPDATE',
  'OUTPUT_ACCEPTED',
  'OUTPUT_REJECTED',
  'PROPOSAL_RECORDED',
  'RETRY',
  'CIRCUIT_OPEN',
  'RUNTIME_FAILED',
  'PROPOSAL_APPROVED',
  'PROPOSAL_REJECTED',
  'DRAFT_APPLICATION_COMPLETED',
  'RUN_CANCELLED',
] as const;

export type StreamState = 'connecting' | 'open' | 'reconnecting' | 'polling' | 'closed';

/** EventSource 的最小子集,便于测试时注入假实现。 */
export interface EventSourceLike {
  readonly readyState: number;
  onopen: ((event: Event) => void) | null;
  onerror: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  addEventListener(type: string, listener: (event: MessageEvent) => void): void;
  close(): void;
}

/** EventSource.CLOSED 的值;测试环境(jsdom)可能没有全局 EventSource,所以不引用常量。 */
const READY_CLOSED = 2;

export interface StreamOptions {
  runId: string;
  onEvent: (event: RunEvent) => void;
  onState: (state: StreamState, attempt: number) => void;
  /** 回退轮询时执行(刷新 run 与 budget)。 */
  poll?: () => Promise<void> | void;
  /** 返回 true 时轮询空转(run 已终态)。 */
  shouldStop?: () => boolean;
  createSource?: (url: string) => EventSourceLike;
  /**
   * 取一次性连接票据(POST /auth/events-ticket/{run_id})。每次(重)连接都会调用;
   * 返回空字符串表示离线演示模式,此时不加 ticket 参数。票据不写日志、不进界面。
   */
  getTicket?: () => Promise<string>;
  /** 连续失败多少次后改为轮询,默认 3。 */
  maxReconnects?: number;
  /** 手动重连的退避(ms),按次数取,超出取最后一个。 */
  backoffMs?: readonly number[];
  pollIntervalMs?: number;
  /** 轮询多久后再尝试恢复 SSE,默认 30s。 */
  retrySseAfterMs?: number;
}

export interface RunEventStream {
  close: () => void;
  lastEventId: () => string | null;
}

function defaultCreate(url: string): EventSourceLike {
  return new EventSource(url) as unknown as EventSourceLike;
}

/** 把一次 SSE 消息规范化为 RunEvent;无法解析时返回 null(丢弃,不抛错)。 */
export function normalizeEvent(message: MessageEvent, runId: string): RunEvent | null {
  let data: unknown;
  try {
    data = JSON.parse(String(message.data));
  } catch {
    return null;
  }
  if (!isRecord(data)) return null;
  const eventId = str(data.event_id) ?? (message.lastEventId ? message.lastEventId : null);
  if (eventId === null) return null;
  const typeFromName = message.type && message.type !== 'message' ? message.type : null;
  return {
    event_id: eventId,
    run_id: str(data.run_id) ?? runId,
    event_type: str(data.event_type) ?? typeFromName ?? 'UNKNOWN',
    occurred_at: str(data.occurred_at) ?? '',
    payload: isRecord(data.payload) ? data.payload : {},
  };
}

export function openRunEventStream(options: StreamOptions): RunEventStream {
  const create = options.createSource ?? defaultCreate;
  const maxReconnects = options.maxReconnects ?? 3;
  const backoff = options.backoffMs ?? [1000, 2000, 5000];
  const pollInterval = options.pollIntervalMs ?? 5000;
  const retryAfter = options.retrySseAfterMs ?? 30000;

  let source: EventSourceLike | null = null;
  let lastId: string | null = null;
  let attempts = 0;
  let closed = false;
  // 每次 connect/close/startPolling 都让旧的异步取票结果作废。
  let generation = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const setState = (state: StreamState) => options.onState(state, attempts);

  const dropSource = () => {
    if (!source) return;
    source.onopen = null;
    source.onerror = null;
    source.onmessage = null;
    source.close();
    source = null;
  };

  const clearTimers = () => {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (retryTimer) clearTimeout(retryTimer);
    if (pollTimer) clearInterval(pollTimer);
    reconnectTimer = retryTimer = null;
    pollTimer = null;
  };

  const handle = (message: MessageEvent) => {
    if (closed) return;
    const event = normalizeEvent(message, options.runId);
    if (!event) return;
    lastId = message.lastEventId || event.event_id;
    options.onEvent(event);
  };

  const runPoll = async () => {
    if (closed || options.shouldStop?.()) return;
    try {
      await options.poll?.();
    } catch {
      // 轮询失败不终止循环;下一轮继续。
    }
  };

  const startPolling = () => {
    generation += 1;
    dropSource();
    clearTimers();
    setState('polling');
    void runPoll();
    pollTimer = setInterval(() => void runPoll(), pollInterval);
    retryTimer = setTimeout(() => {
      if (closed) return;
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = null;
      attempts = 0;
      connect(true);
    }, retryAfter);
  };

  /** 失败统一处理:超过上限回退轮询;manual=true 时自己按退避重建(并重新取票)。 */
  function fail(manual: boolean) {
    attempts += 1;
    if (attempts > maxReconnects) {
      startPolling();
      return;
    }
    if (manual) {
      dropSource();
      setState('reconnecting');
      const wait = backoff[Math.min(attempts - 1, backoff.length - 1)] ?? 1000;
      reconnectTimer = setTimeout(() => connect(true), wait);
      return;
    }
    // 浏览器会自动重连(带 Last-Event-ID);这里只更新状态。
    setState('reconnecting');
  }

  function openSource(ticket: string) {
    if (closed) return;
    // 原生自动重连由浏览器自带 Last-Event-ID 请求头;手动重建连接时用 after_event_id 续传。
    const src = create(runEventsUrl(options.runId, lastId ?? undefined, ticket || undefined));
    source = src;
    // 带票据的连接不能依赖浏览器自动重连(会复用已过期的旧票据),一律手动重建并重新取票。
    const ticketed = ticket !== '';
    src.onopen = () => {
      if (source !== src || closed) return;
      attempts = 0;
      setState('open');
    };
    src.onmessage = handle;
    for (const type of EVENT_TYPES) src.addEventListener(type, handle);
    src.onerror = () => {
      if (source !== src || closed) return;
      fail(ticketed || src.readyState === READY_CLOSED);
    };
  }

  function connect(resuming: boolean) {
    if (closed) return;
    dropSource();
    const mine = ++generation;
    setState(resuming ? 'reconnecting' : 'connecting');
    if (!options.getTicket) {
      openSource('');
      return;
    }
    options.getTicket().then(
      ticket => {
        if (closed || mine !== generation) return;
        openSource(ticket);
      },
      () => {
        if (closed || mine !== generation) return;
        // 取票失败(网络/服务端)按一次连接失败处理;401 已由请求层统一回登录页。
        fail(true);
      },
    );
  }

  connect(false);

  return {
    close: () => {
      if (closed) return;
      closed = true;
      generation += 1;
      clearTimers();
      dropSource();
      setState('closed');
    },
    lastEventId: () => lastId,
  };
}
