import type { ReactNode } from 'react';
import type { AsyncResult } from '../lib/use-async';
import { describeError } from '../lib/errors';
import { Button } from './ui';
import { ErrorDetails } from './error-details';

export function LoadingView({ label = '正在加载…' }: { label?: string }) {
  return (
    <div className="state state--loading" role="status" aria-live="polite">
      <span className="state__dot" aria-hidden="true" />
      {label}
    </div>
  );
}

export function EmptyView({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="state state--empty">
      <p className="state__title">{title}</p>
      {children ? <div className="state__body">{children}</div> : null}
      {action ? <div className="state__action">{action}</div> : null}
    </div>
  );
}

export function ErrorView({ error, onRetry, title = '加载失败' }: { error: unknown; onRetry?: () => void; title?: string }) {
  const info = describeError(error);
  return (
    <div className="state state--error" role="alert">
      <p className="state__title">
        <span aria-hidden="true">✕ </span>
        {title}
      </p>
      <p className="state__body">{info.message}</p>
      {info.code ? (
        <p className="state__meta">
          错误码 <code>{info.code}</code>
          {info.status ? <> · HTTP {info.status}</> : null}
        </p>
      ) : null}
      <ErrorDetails details={info.details} />
      {onRetry ? (
        <div className="state__action">
          <Button variant="secondary" onClick={onRetry}>
            重试
          </Button>
        </div>
      ) : null}
    </div>
  );
}

interface AsyncViewProps<T> {
  result: AsyncResult<T>;
  /** 数据为空时返回 EmptyView 内容;返回 null 表示非空。 */
  empty?: (data: T) => ReactNode | null;
  loadingLabel?: string;
  errorTitle?: string;
  children: (data: T) => ReactNode;
}

/** 统一三态:loading / error(带重试)/ empty;其余渲染 children。 */
export function AsyncView<T>({ result, empty, loadingLabel, errorTitle, children }: AsyncViewProps<T>) {
  const { state, reload } = result;
  if (state.status === 'loading') return <LoadingView label={loadingLabel} />;
  if (state.status === 'error') return <ErrorView error={state.error} onRetry={reload} title={errorTitle} />;
  const emptyNode = empty?.(state.data) ?? null;
  if (emptyNode) return <>{emptyNode}</>;
  return <>{children(state.data)}</>;
}
