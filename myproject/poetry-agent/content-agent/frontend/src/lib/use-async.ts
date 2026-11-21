import { useCallback, useEffect, useRef, useState } from 'react';
import { isAbortError } from '../api/client';

export type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'error'; error: unknown }
  | { status: 'ready'; data: T };

export interface AsyncResult<T> {
  state: AsyncState<T>;
  /** 重新加载并显示 loading(重试按钮用)。 */
  reload: () => void;
  /** 保留旧数据静默刷新(轮询、写入成功后)。失败时保留旧数据。 */
  refresh: () => void;
  refreshing: boolean;
}

/** 请求可取消:依赖变化或卸载时 abort,避免过期响应覆盖新状态。 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): AsyncResult<T> {
  const loadRef = useRef(load);
  loadRef.current = load;
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' });
  const [tick, setTick] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const soft = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    const isSoft = soft.current;
    soft.current = false;
    if (isSoft) setRefreshing(true);
    else setState({ status: 'loading' });
    loadRef.current(controller.signal).then(
      data => {
        if (controller.signal.aborted) return;
        setState({ status: 'ready', data });
        setRefreshing(false);
      },
      error => {
        if (controller.signal.aborted || isAbortError(error)) return;
        setRefreshing(false);
        if (!isSoft) setState({ status: 'error', error });
      },
    );
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  const reload = useCallback(() => {
    soft.current = false;
    setTick(t => t + 1);
  }, []);
  const refresh = useCallback(() => {
    soft.current = true;
    setTick(t => t + 1);
  }, []);
  return { state, reload, refresh, refreshing };
}
