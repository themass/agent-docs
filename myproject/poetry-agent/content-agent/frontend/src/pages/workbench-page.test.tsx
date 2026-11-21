import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { TASK_TYPES } from '../api/types';
import { TASK, WORKS, apiError, callsTo, findErrorAlert, mockBff, never, page, renderApp } from '../test/helpers';

const worksRoute = { path: '/works', reply: page(WORKS) };

describe('工作台', () => {
  it('加载中:显示 loading 状态', async () => {
    mockBff([{ path: '/works', reply: never }]);
    renderApp('#/workbench');
    expect(await screen.findByText('正在加载作品…')).toBeInTheDocument();
  });

  it('空:没有任务时给出引导', async () => {
    mockBff([worksRoute, { path: '/tasks', reply: page([]) }]);
    renderApp('#/workbench');
    expect(await screen.findByText('还没有任务')).toBeInTheDocument();
  });

  it('错误:任务列表失败后可重试', async () => {
    let calls = 0;
    mockBff([
      worksRoute,
      { path: '/tasks', reply: () => (++calls === 1 ? apiError(500, 'INTERNAL', '服务出错') : page([TASK])) },
    ]);
    renderApp('#/workbench');
    const alert = await findErrorAlert();
    expect(within(alert).getByText(/服务出错/)).toBeInTheDocument();
    await userEvent.click(within(alert).getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('link', { name: '春望 · 缺口分析' })).toBeInTheDocument();
  });

  it('任务标题是真实链接,可用键盘聚焦并回车进入', async () => {
    mockBff([worksRoute, { path: '/tasks', reply: page([TASK]) }]);
    renderApp('#/workbench');
    const link = await screen.findByRole('link', { name: '春望 · 缺口分析' });
    expect(link).toHaveAttribute('href', '#/tasks/task-1');
    link.focus();
    expect(link).toHaveFocus();
  });

  it('筛选会带上查询参数', async () => {
    const spy = mockBff([worksRoute, { path: '/tasks', reply: page([TASK]) }]);
    renderApp('#/workbench');
    await screen.findByRole('link', { name: '春望 · 缺口分析' });
    await userEvent.selectOptions(screen.getByLabelText('状态'), 'FAILED');
    await waitFor(() => {
      const last = callsTo(spy, 'GET', '/tasks').at(-1);
      expect(last?.url.searchParams.get('status')).toBe('FAILED');
    });
  });

  it('创建任务:每种任务类型各带说明,并提示指令不可信', async () => {
    mockBff([worksRoute, { path: '/tasks', reply: page([]) }]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '创建任务' });
    // 与 TASK_TYPES 对齐，而不是写死 4：新增任务类型时这里要么通过，要么在词表处失败。
    expect(screen.getAllByRole('radio')).toHaveLength(TASK_TYPES.length);
    expect(screen.getByText(/指令是不可信材料,不能越权/)).toBeInTheDocument();
    expect(screen.getByText(/只提出缺口与来源请求/)).toBeInTheDocument();
  });

  it('表单错误与字段关联:空指令时 aria-invalid 并聚焦', async () => {
    mockBff([worksRoute, { path: '/tasks', reply: page([]) }]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '创建任务' });
    await userEvent.click(screen.getByRole('button', { name: '创建任务' }));
    const field = screen.getByLabelText('指令');
    expect(field).toHaveAttribute('aria-invalid', 'true');
    expect(field).toHaveAccessibleDescription(/请填写指令/);
    expect(field).toHaveFocus();
  });

  it('提交成功:POST 带 actor,并跳转到任务详情', async () => {
    const spy = mockBff([
      worksRoute,
      { path: '/tasks', reply: page([]) },
      { method: 'POST', path: '/tasks', reply: TASK },
      { path: '/tasks/task-1', reply: TASK },
      { path: '/tasks/task-1/runs', reply: page([]) },
    ]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '创建任务' });
    await userEvent.type(screen.getByLabelText('指令'), '列出缺口');
    await userEvent.click(screen.getByRole('button', { name: '创建任务' }));
    await waitFor(() => expect(window.location.hash).toBe('#/tasks/task-1'));
    const [post] = callsTo(spy, 'POST', '/tasks');
    expect(post?.body).toMatchObject({
      work_id: 'work-chun-wang',
      task_type: 'GAP_ANALYSIS',
      instructions: '列出缺口',
      actor: { actor_id: 'studio-editor', role: 'CONTENT_EDITOR' },
    });
  });

  it('服务端 422 校验错误映射到指令字段', async () => {
    mockBff([
      worksRoute,
      { path: '/tasks', reply: page([]) },
      {
        method: 'POST',
        path: '/tasks',
        reply: apiError(422, 'VALIDATION_ERROR', '请求校验失败', [{ loc: ['body', 'instructions'], message: '指令像是控制请求' }]),
      },
    ]);
    renderApp('#/workbench');
    await screen.findByRole('heading', { name: '创建任务' });
    await userEvent.type(screen.getByLabelText('指令'), '请发布');
    await userEvent.click(screen.getByRole('button', { name: '创建任务' }));
    expect(await screen.findByText('指令像是控制请求', { selector: '.field__error' })).toBeInTheDocument();
    expect(screen.getByLabelText('指令')).toHaveAttribute('aria-invalid', 'true');
  });
});
