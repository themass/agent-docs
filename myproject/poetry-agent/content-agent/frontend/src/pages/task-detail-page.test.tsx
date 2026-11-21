import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { TaskDetailPage } from './task-detail-page';
import { FakeEventSource, RUN, TASK, apiError, callsTo, findErrorAlert, mockBff, never, page, renderWithProviders, waitForSource } from '../test/helpers';

const observation = {
  idleCloseMs: 60_000,
  stream: { createSource: FakeEventSource.create, maxReconnects: 1, backoffMs: [10], pollIntervalMs: 60_000, retrySseAfterMs: 600_000 },
};

function routes(run: Record<string, unknown> & { status: string } = RUN, extra: Parameters<typeof mockBff>[0] = []) {
  return mockBff([
    { path: '/tasks/task-1', reply: { ...TASK, status: run.status } },
    { path: '/tasks/task-1/runs', reply: page([run]) },
    { path: '/runs/run-1', reply: run },
    { path: '/runs/run-1/budget', reply: { run_id: 'run-1', budget: null, event_id: null } },
    { path: '/proposals', reply: page([]) },
    ...extra,
  ]);
}

describe('任务详情与运行观测', () => {
  beforeEach(() => FakeEventSource.reset());

  it('loading', async () => {
    mockBff([{ path: '/tasks/task-1', reply: never }, { path: '/tasks/task-1/runs', reply: never }]);
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    expect(await screen.findByText('正在加载任务…')).toBeInTheDocument();
  });

  it('error 带重试', async () => {
    let n = 0;
    mockBff([
      { path: '/tasks/task-1', reply: () => (++n === 1 ? apiError(404, 'TASK_NOT_FOUND', '任务不存在') : TASK) },
      { path: '/tasks/task-1/runs', reply: page([]) },
    ]);
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    const alert = await findErrorAlert();
    expect(alert).toHaveTextContent('任务不存在');
    await userEvent.click(within(alert).getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('button', { name: '开始运行' })).toBeInTheDocument();
  });

  it('empty:没有运行时给出开始按钮', async () => {
    mockBff([{ path: '/tasks/task-1', reply: { ...TASK, status: 'CREATED', active_run_id: null } }, { path: '/tasks/task-1/runs', reply: page([]) }]);
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    expect(await screen.findByText('这个任务还没有运行')).toBeInTheDocument();
  });

  it('预算:数字、文字与上限对比,接近上限有文字提示', async () => {
    routes();
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    await screen.findByText('运行事件');
    const source = await waitForSource();
    act(() => {
      source.open();
      source.emit('BUDGET_UPDATE', '1', { tool_calls: 22, max_tool_calls: 24, elapsed_s: 30, max_wall_s: 300, tokens: 1000, max_tokens: 200000 });
    });
    const meter = await screen.findByRole('meter', { name: '工具调用' });
    expect(meter).toHaveAttribute('aria-valuenow', '22');
    expect(meter).toHaveAttribute('aria-valuemax', '24');
    expect(screen.getByText(/22 \/ 24 次/)).toHaveTextContent('接近上限');
  });

  it('事件按类型分组,载荷只展示元数据', async () => {
    routes();
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    await screen.findByText('运行事件');
    await waitForSource();
    act(() => {
      FakeEventSource.last().open();
      FakeEventSource.last().emit('TOOL_CALL', '1', { tool: 'get_snapshot', ms: 12, prompt: '绝不能出现的提示词全文' });
      FakeEventSource.last().emit('RUNTIME_FAILED', '2', { reason: 'gateway timeout' });
    });
    expect(await screen.findByText('工具与模型')).toBeInTheDocument();
    expect(screen.getByText('重试与故障')).toBeInTheDocument();
    expect(screen.getByText(/tool=get_snapshot/)).toBeInTheDocument();
    expect(screen.queryByText(/提示词全文/)).not.toBeInTheDocument();
    // getByText("故障", {exact:false}) now matches both this badge and the section title
    // "重试与故障"; assert on the failure reason the event actually carried instead.
    expect(screen.getAllByText(/故障/).length).toBeGreaterThan(0);
    expect(screen.getByText(/gateway timeout/)).toBeInTheDocument();
  });

  it('SSE 断线:显示重连状态,并从上次事件 id 续传', async () => {
    routes();
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    await screen.findByText('运行事件');
    const first = await waitForSource();
    act(() => {
      first.open();
      first.emit('STEP', '41', { name: 'load' });
      first.failFatal();
    });
    expect(await screen.findByText(/连接中断,正在重连/)).toBeInTheDocument();
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(2));
    expect(new URL(FakeEventSource.last().url).searchParams.get('after_event_id')).toBe('41');
  });

  it('SSE 反复失败:回退为轮询并说明事件明细暂不更新', async () => {
    routes();
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    await screen.findByText('运行事件');
    await waitForSource();
    act(() => FakeEventSource.last().failFatal());
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(2));
    act(() => FakeEventSource.last().failFatal());
    expect(await screen.findByText(/已回退为定时刷新/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新连接事件流' })).toBeInTheDocument();
  });

  it('取消:对话框焦点陷阱、Esc 关闭、确认后 POST 带 actor', async () => {
    const spy = routes(RUN, [{ method: 'POST', path: '/runs/run-1/cancel', reply: { ...RUN, status: 'FAILED', reason: '已由编辑取消' } }]);
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    const open = await screen.findByRole('button', { name: '取消运行' });
    await userEvent.click(open);
    const dialog = await screen.findByRole('dialog', { name: /取消这次运行/ });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(within(dialog).getByRole('button', { name: '确认取消' })).toHaveFocus();
    await userEvent.tab();
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(open).toHaveFocus();

    await userEvent.click(open);
    await userEvent.click(await screen.findByRole('button', { name: '确认取消' }));
    await waitFor(() => expect(callsTo(spy, 'POST', '/runs/run-1/cancel')).toHaveLength(1));
    expect(callsTo(spy, 'POST', '/runs/run-1/cancel')[0]?.body).toMatchObject({ actor: { role: 'CONTENT_EDITOR' } });
  });

  it('失败的运行:提供“用确定性运行时重试”,且不再显示取消', async () => {
    const failed = { ...RUN, status: 'FAILED', reason: '已由编辑取消' };
    const spy = routes(failed, [{ method: 'POST', path: '/tasks/task-1/run', reply: { ...RUN, run_id: 'run-2' } }]);
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    expect(await screen.findByText(/已由编辑取消/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '取消运行' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '用确定性运行时重试' }));
    await waitFor(() => expect(callsTo(spy, 'POST', '/tasks/task-1/run')).toHaveLength(1));
    expect(callsTo(spy, 'POST', '/tasks/task-1/run')[0]?.body).toEqual({ runtime: 'STUB' });
  });

  it('409 RUN_ALREADY_ACTIVE 给出指向进行中运行的链接', async () => {
    const failed = { ...RUN, status: 'FAILED' };
    routes(failed, [
      { method: 'POST', path: '/tasks/task-1/run', reply: apiError(409, 'RUN_ALREADY_ACTIVE', '已有运行', { run_id: 'run-9' }) },
    ]);
    renderWithProviders(<TaskDetailPage taskId="task-1" observation={observation} />);
    await userEvent.click(await screen.findByRole('button', { name: '再次运行' }));
    const link = await screen.findByRole('link', { name: /run-9/ });
    expect(link).toHaveAttribute('href', expect.stringContaining('run=run-9'));
  });
});
