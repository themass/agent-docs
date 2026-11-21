import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearSession, getToken, setSession } from './api/session';
import { FakeEventSource, OFF_ME, RUN, TASK, WORKS, apiError, authHeaderOf, callsTo, findErrorAlert, json, mockBff, never, page, renderApp, requiredMe, waitForSource } from './test/helpers';

const works = { path: '/works', reply: page(WORKS) };
const tasks = { path: '/tasks', reply: page([TASK]) };
const loginOk = {
  token: 'secret-token-value',
  expires_at: Math.floor(Date.now() / 1000) + 3600,
  actor: { actor_id: 'li-wen', role: 'HISTORICAL_REVIEWER', name: '李文' },
};

/** 启动时无令牌 → 401;登录后 → 200(模拟服务端)。 */
function requiredBff(extra: Parameters<typeof mockBff>[0] = []) {
  return mockBff([
    {
      path: '/auth/me',
      reply: () => (getToken() ? requiredMe('HISTORICAL_REVIEWER') : apiError(401, 'AUTH_REQUIRED', '需要登录')),
    },
    { method: 'POST', path: '/auth/login', reply: loginOk },
    works,
    tasks,
    ...extra,
  ]);
}

describe('启动与离线演示模式', () => {
  beforeEach(() => clearSession());

  it('启动先确认登录状态(loading)', async () => {
    mockBff([{ path: '/auth/me', reply: never }]);
    renderApp('#/workbench');
    expect(await screen.findByText('正在确认登录状态…')).toBeInTheDocument();
  });

  it('确认失败(网络/服务端)显示错误并可重试', async () => {
    let n = 0;
    mockBff([{ path: '/auth/me', reply: () => (++n === 1 ? apiError(500, 'INTERNAL', '服务出错') : OFF_ME) }, works, tasks]);
    renderApp('#/workbench');
    const alert = await findErrorAlert();
    expect(alert).toHaveTextContent('服务出错');
    await userEvent.click(within(alert).getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('navigation', { name: '主导航' })).toBeInTheDocument();
  });

  it('auth_mode=off:页首醒目横幅(文案取自 warning),保留占位身份选择器,不加 Authorization', async () => {
    const spy = mockBff([{ path: '/auth/me', reply: { auth_mode: 'off', warning: '这是演示环境,任何人都能操作' } }, works, tasks]);
    renderApp('#/workbench');
    const banner = await screen.findByRole('region', { name: '离线演示模式' });
    expect(banner).toHaveTextContent('这是演示环境,任何人都能操作');
    expect(screen.getByRole('button', { name: /studio-editor/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '退出登录' })).not.toBeInTheDocument();
    // The banner can render before the works request goes out; wait for the request instead of racing it.
    await waitFor(() => expect(spy.mock.calls.some(([url]) => String(url).includes('/works'))).toBe(true));
    const calls = spy.mock.calls.filter(([url]) => String(url).includes('/works'));
    for (const call of calls) expect(authHeaderOf(call as [RequestInfo | URL, RequestInit | undefined])).toBeUndefined();
  });

  it('off 模式创建任务时请求体带 actor', async () => {
    const spy = mockBff([works, { path: '/tasks', reply: page([]) }, { method: 'POST', path: '/tasks', reply: TASK }, { path: '/tasks/task-1', reply: TASK }, { path: '/tasks/task-1/runs', reply: page([]) }]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '创建任务' });
    await userEvent.type(screen.getByLabelText('指令'), '列出缺口');
    await userEvent.click(screen.getByRole('button', { name: '创建任务' }));
    await waitFor(() => expect(callsTo(spy, 'POST', '/tasks')).toHaveLength(1));
    expect(callsTo(spy, 'POST', '/tasks')[0]?.body).toHaveProperty('actor');
  });
});

describe('登录页', () => {
  beforeEach(() => clearSession());

  it('401 AUTH_REQUIRED 启动时进入登录页,标签与输入关联,密码框 autocomplete', async () => {
    requiredBff();
    renderApp('#/workbench');
    expect(await screen.findByRole('heading', { name: '登录' })).toBeInTheDocument();
    const user = screen.getByLabelText('账号');
    const pass = screen.getByLabelText('密码');
    expect(user).toHaveFocus();
    expect(pass).toHaveAttribute('type', 'password');
    expect(pass).toHaveAttribute('autocomplete', 'current-password');
    expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument();
  });

  it('空表单:字段错误与输入关联,并聚焦第一个错误字段', async () => {
    requiredBff();
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '登录' });
    await userEvent.click(screen.getByRole('button', { name: '登录' }));
    const user = screen.getByLabelText('账号');
    expect(user).toHaveAttribute('aria-invalid', 'true');
    // No "✕ " in the accessible description: Field renders it inside aria-hidden="true",
    // which by design is excluded from what a screen reader announces.
    expect(user).toHaveAccessibleDescription('请输入账号。');
    expect(user).toHaveFocus();
  });

  it('键盘:输入账号、Tab 到密码、Enter 提交;令牌只进 sessionStorage,不进 localStorage', async () => {
    const spy = requiredBff();
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '登录' });
    await userEvent.type(screen.getByLabelText('账号'), 'li-wen');
    await userEvent.tab();
    expect(screen.getByLabelText('密码')).toHaveFocus();
    await userEvent.keyboard('correct horse{Enter}');

    expect(await screen.findByRole('navigation', { name: '主导航' })).toBeInTheDocument();
    expect(callsTo(spy, 'POST', '/auth/login')[0]?.body).toEqual({ user_id: 'li-wen', password: 'correct horse' });
    expect(window.sessionStorage.getItem('poetry-studio.token')).toBe('secret-token-value');
    expect(JSON.stringify({ ...window.localStorage })).not.toContain('secret-token-value');
    // 登录成功后界面里不出现令牌或密码
    expect(document.body.textContent).not.toContain('secret-token-value');
    expect(document.body.textContent).not.toContain('correct horse');
  });

  it('登录后:所有请求带 Bearer,顶部显示姓名与中文角色名,required 模式创建任务不带 actor', async () => {
    const spy = requiredBff([{ method: 'POST', path: '/tasks', reply: TASK }, { path: '/tasks/task-1', reply: TASK }, { path: '/tasks/task-1/runs', reply: page([]) }]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '登录' });
    await userEvent.type(screen.getByLabelText('账号'), 'li-wen');
    await userEvent.type(screen.getByLabelText('密码'), 'pw{Enter}');
    await screen.findByRole('navigation', { name: '主导航' });
    expect(screen.getByText('李文')).toBeInTheDocument();
    expect(screen.getByText('史料审核人')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '离线演示模式' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /占位身份/ })).not.toBeInTheDocument();

    const afterLogin = spy.mock.calls.filter(([url]) => String(url).endsWith('/works?limit=200'));
    expect(afterLogin.length).toBeGreaterThan(0);
    expect(authHeaderOf(afterLogin.at(-1) as [RequestInfo | URL, RequestInit | undefined])).toBe('Bearer secret-token-value');

    await screen.findByRole('heading', { name: '创建任务' });
    await userEvent.type(screen.getByLabelText('指令'), '列出缺口');
    await userEvent.click(screen.getByRole('button', { name: '创建任务' }));
    await waitFor(() => expect(callsTo(spy, 'POST', '/tasks')).toHaveLength(1));
    expect(callsTo(spy, 'POST', '/tasks')[0]?.body).not.toHaveProperty('actor');
  });

  it('LOGIN_FAILED:统一提示“账号或密码不正确”,清空密码,不回显', async () => {
    mockBff([{ path: '/auth/me', reply: apiError(401, 'AUTH_REQUIRED', '需要登录') }, { method: 'POST', path: '/auth/login', reply: apiError(401, 'LOGIN_FAILED', 'user not found') }]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '登录' });
    await userEvent.type(screen.getByLabelText('账号'), 'nobody');
    await userEvent.type(screen.getByLabelText('密码'), 'wrong-pass{Enter}');
    const alert = await findErrorAlert();
    expect(alert).toHaveTextContent('账号或密码不正确。');
    expect(alert).not.toHaveTextContent('user not found');
    expect(screen.getByLabelText('密码')).toHaveValue('');
    expect(document.body.textContent).not.toContain('wrong-pass');
  });

  it('LOGIN_LOCKED:读 Retry-After 显示倒计时并暂时禁用提交', async () => {
    mockBff([
      { path: '/auth/me', reply: apiError(401, 'AUTH_REQUIRED', '需要登录') },
      { method: 'POST', path: '/auth/login', reply: apiError(429, 'LOGIN_LOCKED', 'locked', undefined, { 'Retry-After': '30' }) },
    ]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '登录' });
    await userEvent.type(screen.getByLabelText('账号'), 'li-wen');
    await userEvent.type(screen.getByLabelText('密码'), 'pw{Enter}');
    expect(await screen.findByRole('timer')).toHaveTextContent('30');
    expect(screen.getByRole('button', { name: /已锁定/ })).toHaveAttribute('aria-disabled', 'true');
  });

  it('AUTH_NOT_CONFIGURED 提示联系管理员;AUTH_DISABLED 说明是离线演示并可重新检查', async () => {
    mockBff([{ path: '/auth/me', reply: apiError(401, 'AUTH_REQUIRED', '需要登录') }, { method: 'POST', path: '/auth/login', reply: apiError(503, 'AUTH_NOT_CONFIGURED', 'x') }]);
    const first = renderApp('#/workbench');
    await screen.findByRole('heading', { name: '登录' });
    await userEvent.type(screen.getByLabelText('账号'), 'a1');
    await userEvent.type(screen.getByLabelText('密码'), 'pw{Enter}');
    expect(await findErrorAlert()).toHaveTextContent('联系管理员');
    first.unmount();

    mockBff([{ path: '/auth/me', reply: apiError(401, 'AUTH_REQUIRED', '需要登录') }, { method: 'POST', path: '/auth/login', reply: apiError(409, 'AUTH_DISABLED', 'x') }]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '登录' });
    await userEvent.type(screen.getByLabelText('账号'), 'a1');
    await userEvent.type(screen.getByLabelText('密码'), 'pw{Enter}');
    const alert = await findErrorAlert();
    expect(alert).toHaveTextContent('离线演示模式');
    expect(within(alert).getByRole('button', { name: '重新检查并进入' })).toBeInTheDocument();
  });
});

describe('会话', () => {
  beforeEach(() => clearSession());

  it('已有有效令牌:/auth/me 返回 200 直接进入,显示姓名与角色', async () => {
    setSession('tok', Math.floor(Date.now() / 1000) + 600);
    mockBff([{ path: '/auth/me', reply: requiredMe('CONTENT_EDITOR', 'wang-shi', '王石') }, works, tasks]);
    renderApp('#/workbench');
    expect(await screen.findByText('王石')).toBeInTheDocument();
    expect(screen.getByText('内容编辑')).toBeInTheDocument();
  });

  it('任何请求收到 401 AUTH_REQUIRED:清令牌、回登录页,并保留当前 hash', async () => {
    setSession('tok', Math.floor(Date.now() / 1000) + 600);
    let expired = false;
    mockBff([
      { path: '/auth/me', reply: () => (expired ? apiError(401, 'AUTH_REQUIRED', 'x') : requiredMe()) },
      works,
      { path: '/tasks', reply: () => (expired ? apiError(401, 'AUTH_REQUIRED', '令牌失效') : page([TASK])) },
      { path: '/proposals', reply: () => (expired ? apiError(401, 'AUTH_REQUIRED', '令牌失效') : page([])) },
    ]);
    renderApp('#/workbench');
    await screen.findByRole('link', { name: '春望 · 缺口分析' });
    expired = true;
    act(() => {
      window.location.hash = '#/proposals?status=APPROVED';
    });
    expect(await screen.findByRole('heading', { name: '登录' })).toBeInTheDocument();
    expect(screen.getByText('登录已失效,请重新登录。')).toBeInTheDocument();
    expect(window.sessionStorage.getItem('poetry-studio.token')).toBeNull();
    expect(window.location.hash).toBe('#/proposals?status=APPROVED');
  });

  it('令牌到期:不静默续期,回到登录页', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      setSession('tok', Math.floor(Date.now() / 1000) + 5);
      mockBff([{ path: '/auth/me', reply: requiredMe() }, works, tasks]);
      renderApp('#/workbench');
      await screen.findByText('李文');
      await act(async () => {
        await vi.advanceTimersByTimeAsync(6000);
      });
      expect(await screen.findByText('登录已过期,请重新登录。')).toBeInTheDocument();
      expect(getToken()).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('退出登录:清令牌,回到登录页', async () => {
    setSession('tok', Math.floor(Date.now() / 1000) + 600);
    mockBff([{ path: '/auth/me', reply: requiredMe() }, works, tasks]);
    renderApp('#/workbench');
    await userEvent.click(await screen.findByRole('button', { name: '退出登录' }));
    expect(await screen.findByRole('heading', { name: '登录' })).toBeInTheDocument();
    expect(window.sessionStorage.getItem('poetry-studio.token')).toBeNull();
    // Appears in the login page notice and in the sr-only announcer; either proves the message was sent.
    expect(screen.getAllByText('已退出登录。').length).toBeGreaterThan(0);
  });

  it('required 模式用 /auth/me 的角色决定按钮禁用,而不是本地存储', async () => {
    setSession('tok', Math.floor(Date.now() / 1000) + 600);
    window.localStorage.setItem('poetry-studio.actor', JSON.stringify({ actor_id: 'x1', role: 'CONTENT_EDITOR' }));
    const proposal = { proposal_id: 'proposal_1', work_id: 'work-chun-wang', run_id: 'run-1', task_id: 'task-1', status: 'REVIEW_REQUIRED', created_at: '2026-11-06T09:30:00Z', payload: { summary: 's' }, items: [], executable_count: 0, approved_executable_count: 0 };
    mockBff([
      { path: '/auth/me', reply: requiredMe('PLATFORM_ADMIN', 'admin-1', '管理员') },
      { path: '/proposals/proposal_1', reply: proposal },
      { path: '/proposals/proposal_1/diff', reply: { proposal_id: 'proposal_1', work_id: 'work-chun-wang', changes: [] } },
    ]);
    renderApp('#/proposals/proposal_1');
    const reject = await screen.findByRole('button', { name: /整体驳回/ });
    expect(reject).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getAllByText(/PLATFORM_ADMIN/).length).toBeGreaterThan(0);
  });
});

describe('SSE 连接票据(页面级)', () => {
  beforeEach(() => {
    FakeEventSource.reset();
    clearSession();
  });

  it('登录模式:POST 取票(带 Bearer)后连接;票据不出现在界面;断线重连重新取票', async () => {
    setSession('tok', Math.floor(Date.now() / 1000) + 600);
    let n = 0;
    const spy = mockBff([
      { path: '/auth/me', reply: requiredMe() },
      { path: '/tasks/task-1', reply: TASK },
      { path: '/tasks/task-1/runs', reply: page([RUN]) },
      { path: '/runs/run-1', reply: RUN },
      { path: '/runs/run-1/budget', reply: { run_id: 'run-1', budget: null, event_id: null } },
      { path: '/proposals', reply: page([]) },
      { method: 'POST', path: '/auth/events-ticket/run-1', reply: () => json({ ticket: `ticket-${++n}`, expires_at: 60 }) },
    ]);
    const { TaskDetailPage } = await import('./pages/task-detail-page');
    const { render } = await import('@testing-library/react');
    const { AnnouncerProvider } = await import('./components/announcer');
    const { AuthProvider } = await import('./lib/actor');
    render(
      <AnnouncerProvider>
        <AuthProvider>
          <TaskDetailPage
            taskId="task-1"
            observation={{ idleCloseMs: 60_000, stream: { createSource: FakeEventSource.create, maxReconnects: 3, backoffMs: [10], pollIntervalMs: 60_000, retrySseAfterMs: 600_000 } }}
          />
        </AuthProvider>
      </AnnouncerProvider>,
    );

    const first = await waitForSource();
    expect(new URL(first.url).searchParams.get('ticket')).toBe('ticket-1');
    const ticketCall = callsTo(spy, 'POST', '/auth/events-ticket/run-1');
    expect(ticketCall).toHaveLength(1);
    const raw = spy.mock.calls.find(([url, init]) => String(url).includes('events-ticket') && init?.method === 'POST');
    expect(authHeaderOf(raw as [RequestInfo | URL, RequestInit | undefined])).toBe('Bearer tok');

    act(() => {
      first.open();
      first.emit('STEP', '8');
      first.failFatal();
    });
    await waitForSource(2);
    const second = FakeEventSource.last();
    const params = new URL(second.url).searchParams;
    expect(params.get('ticket')).toBe('ticket-2');
    expect(params.get('after_event_id')).toBe('8');
    expect(document.body.textContent).not.toContain('ticket-1');
    expect(document.body.textContent).not.toContain('ticket-2');
  });
});
