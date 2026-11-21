import { useCallback, useEffect, useRef, useState } from 'react';
import { getEventsTicket, getRun, getRunBudget, parseBudget } from '../api/client';
import { openRunEventStream, type RunEventStream, type StreamOptions, type StreamState } from '../api/events';
import type { AgentRun, BudgetSummary, RunEvent } from '../api/types';
import { mergeEvents } from './event-view';

/** 契约补充:取消后 run.status=FAILED,所以终态只有这两个。AWAITING_REVIEW 之后仍可能有评审事件。 */
export const TERMINAL_STATUSES: readonly string[] = ['COMPLETED', 'FAILED'];
export const ACTIVE_STATUSES: readonly string[] = ['CREATED', 'RUNNING', 'WAITING_FOR_RUNTIME'];
export const isTerminal = (status: string) => TERMINAL_STATUSES.includes(status);
export const isActive = (status: string) => ACTIVE_STATUSES.includes(status);

/** 这些事件意味着 run 或提案状态可能变了,收到后静默刷新 run。 */
const REFRESH_ON = new Set([
  'RUN_STATE_CHANGED',
  'RUN_CANCELLED',
  'RUNTIME_FAILED',
  'PROPOSAL_RECORDED',
  'PROPOSAL_APPROVED',
  'PROPOSAL_REJECTED',
  'DRAFT_APPLICATION_COMPLETED',
  'OUTPUT_ACCEPTED',
]);

export interface ObservationOptions {
  onStatusChange?: (run: AgentRun) => void;
  onProposalEvent?: () => void;
  /** run 终态后,多久没有新事件就关闭 SSE(服务端不会主动结束流)。默认 6000ms。 */
  idleCloseMs?: number;
  /** 测试注入:假 EventSource 与更短的退避。 */
  stream?: Partial<Pick<StreamOptions, 'createSource' | 'maxReconnects' | 'backoffMs' | 'pollIntervalMs' | 'retrySseAfterMs'>>;
}

export interface Observation {
  run: AgentRun;
  events: RunEvent[];
  budget: BudgetSummary | null;
  stream: { state: StreamState; attempt: number };
  refreshError: boolean;
  reconnect: () => void;
  refreshNow: () => void;
}

export function useRunObservation(initial: AgentRun, options: ObservationOptions = {}): Observation {
  const runId = initial.run_id;
  const [run, setRun] = useState<AgentRun>(initial);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [budget, setBudget] = useState<BudgetSummary | null>(initial.budget ?? null);
  const [stream, setStream] = useState<{ state: StreamState; attempt: number }>({ state: 'connecting', attempt: 0 });
  const [refreshError, setRefreshError] = useState(false);
  const [connectKey, setConnectKey] = useState(0);

  const runRef = useRef(run);
  runRef.current = run;
  const lastStatus = useRef(initial.status);
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const handle = useRef<RunEventStream | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controllers = useRef(new Set<AbortController>());

  const refresh = useCallback(async () => {
    const controller = new AbortController();
    controllers.current.add(controller);
    try {
      const [latest, budgetResponse] = await Promise.all([
        getRun(runId, controller.signal),
        getRunBudget(runId, controller.signal).catch(() => null),
      ]);
      if (controller.signal.aborted) return;
      setRun(latest);
      const nextBudget = budgetResponse?.budget ?? latest.budget ?? null;
      if (nextBudget) setBudget(nextBudget);
      setRefreshError(false);
      if (latest.status !== lastStatus.current) {
        lastStatus.current = latest.status;
        optionsRef.current.onStatusChange?.(latest);
      }
    } catch {
      if (!controller.signal.aborted) setRefreshError(true);
    } finally {
      controllers.current.delete(controller);
    }
  }, [runId]);

  const scheduleRefresh = useCallback(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => void refresh(), 300);
  }, [refresh]);

  // 打开 SSE;断线重连与失败回退轮询在 openRunEventStream 内。
  useEffect(() => {
    const opened = openRunEventStream({
      runId,
      // EventSource 不能带头:先用 Bearer 取一次性票据(off 模式为空串),每次重连都重新取。
      getTicket: async () => (await getEventsTicket(runId)).ticket,
      ...optionsRef.current.stream,
      onEvent: event => {
        setEvents(current => mergeEvents(current, [event]));
        if (event.event_type === 'BUDGET_UPDATE') {
          const parsed = parseBudget(event.payload);
          if (parsed) setBudget(parsed);
        }
        if (event.event_type === 'PROPOSAL_RECORDED') optionsRef.current.onProposalEvent?.();
        if (REFRESH_ON.has(event.event_type)) scheduleRefresh();
      },
      onState: (state, attempt) => setStream({ state, attempt }),
      poll: refresh,
      shouldStop: () => isTerminal(runRef.current.status),
    });
    handle.current = opened;
    return () => {
      opened.close();
      handle.current = null;
    };
  }, [runId, connectKey, refresh, scheduleRefresh]);

  // 进入页面时先刷新一次,避免 initial 已过期。
  useEffect(() => {
    void refresh();
    const live = controllers.current;
    return () => {
      for (const controller of live) controller.abort();
      if (debounce.current) clearTimeout(debounce.current);
    };
  }, [refresh]);

  // 终态后:一段时间没有新事件就关闭流,不再保持“进行中”的假象。
  const terminal = isTerminal(run.status);
  const idleMs = options.idleCloseMs ?? 6000;
  useEffect(() => {
    if (!terminal || stream.state === 'closed') return undefined;
    const timer = setTimeout(() => handle.current?.close(), idleMs);
    return () => clearTimeout(timer);
  }, [terminal, events.length, stream.state, idleMs]);

  const reconnect = useCallback(() => setConnectKey(k => k + 1), []);
  const refreshNow = useCallback(() => void refresh(), [refresh]);

  return { run, events, budget, stream, refreshError, reconnect, refreshNow };
}
