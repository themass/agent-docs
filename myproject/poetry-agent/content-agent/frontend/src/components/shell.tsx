import { useRef, useState, type ReactNode } from 'react';
import { getReadiness } from '../api/client';
import { useActor } from '../lib/actor';
import { ROLE_LABEL } from '../lib/labels';
import { useRoute } from '../lib/router';
import { useAsync } from '../lib/use-async';
import { ActorDialog } from './actor-dialog';
import { ErrorBoundary } from './error-boundary';

export const NAV: { href: string; root: string; label: string }[] = [
  { href: '#/workbench', root: 'workbench', label: '工作台' },
  { href: '#/tasks', root: 'tasks', label: '任务与运行' },
  { href: '#/proposals', root: 'proposals', label: '提案审核' },
  { href: '#/coverage', root: 'coverage', label: '缺口与覆盖' },
  { href: '#/sources', root: 'sources', label: '出处核查' },
  { href: '#/content', root: 'content', label: '作品内容' },
  { href: '#/precheck', root: 'precheck', label: '发布前检查' },
];

function Footer() {
  const result = useAsync(signal => getReadiness(signal), []);
  const state = result.state;
  let text = '正在检查 BFF…';
  if (state.status === 'error') text = 'BFF 不可达';
  else if (state.status === 'ready') {
    const d = state.data;
    text = `BFF 可达 · worker ${d.worker_configured ? '已配置' : '未配置'} · reviewer 通道 ${
      d.reviewer_token_configured ? '已配置' : '未配置'
    }`;
  }
  return (
    <footer className="footer">
      <span>Poetry Studio · 编辑侧工作台,不面向学生。</span>
      <span>{text}</span>
      <span>Agent 只产生 DRAFT 候选;发布权在人和 Java 发布闸门。</span>
    </footer>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const route = useRoute();
  const { actor, name, mode, warning, logout } = useActor();
  const [dialog, setDialog] = useState(false);
  const main = useRef<HTMLElement>(null);
  const root = route.segments[0] ?? 'workbench';

  return (
    <div className="shell">
      <a
        className="skip-link"
        href="#main"
        onClick={event => {
          event.preventDefault();
          main.current?.focus();
        }}
      >
        跳到主要内容
      </a>
      {mode === 'off' ? (
        <div className="demo-banner" role="region" aria-label="离线演示模式">
          <strong>离线演示模式</strong>
          <span>{warning}</span>
        </div>
      ) : null}
      <header className="topbar" role="banner">
        <div className="brand">
          <span className="brand__name">诗词时空</span>
          <span className="brand__sub">POETRY STUDIO</span>
        </div>
        <nav aria-label="主导航" className="nav">
          <ul>
            {NAV.map(item => {
              const current = root === item.root || (item.root === 'workbench' && route.segments.length === 0);
              return (
                <li key={item.href}>
                  <a href={item.href} aria-current={current ? 'page' : undefined}>
                    {item.label}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="topbar__right">
          <span className="env-tag" title="Studio 只能写入 DRAFT">
            AUTHORING · DRAFT ONLY
          </span>
          {mode === 'off' ? (
            <button type="button" className="actor-button" onClick={() => setDialog(true)} aria-haspopup="dialog">
              <span className="actor-button__id">{actor.actor_id}</span>
              <span className="actor-button__role">{ROLE_LABEL[actor.role]}</span>
              <span className="actor-button__hint">占位身份,点击切换</span>
            </button>
          ) : (
            <div className="session">
              <span className="session__who">
                <span className="session__name">{name}</span>
                <span className="session__role">{ROLE_LABEL[actor.role]}</span>
              </span>
              <button type="button" className="btn btn--quiet" onClick={logout}>
                退出登录
              </button>
            </div>
          )}
        </div>
      </header>
      <main id="main" ref={main} tabIndex={-1} className="main">
        <ErrorBoundary resetKey={route.path}>{children}</ErrorBoundary>
      </main>
      <Footer />
      {dialog && mode === 'off' ? <ActorDialog onClose={() => setDialog(false)} /> : null}
    </div>
  );
}
