import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /** 变化时清除错误状态(如路由变化)。 */
  resetKey?: string;
}
interface State {
  error: Error | null;
}

/** 全局错误边界:渲染期异常不白屏,给出可操作的出口。 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 只记元数据到控制台,便于开发排查;不上报、不带用户内容。
    console.error('[studio] render error:', error.message, info.componentStack?.split('\n')[1]?.trim() ?? '');
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="state state--error boundary" role="alert">
        <p className="state__title">
          <span aria-hidden="true">✕ </span>页面出错了
        </p>
        <p className="state__body">{this.state.error.message || '渲染过程中发生未预期的错误。'}</p>
        <div className="state__action">
          <button type="button" className="btn btn--secondary" onClick={() => this.setState({ error: null })}>
            重试
          </button>{' '}
          <a className="btn btn--quiet" href="#/workbench">
            回到工作台
          </a>
        </div>
      </div>
    );
  }
}
