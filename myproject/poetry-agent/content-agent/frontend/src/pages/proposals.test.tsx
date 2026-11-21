import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { DIFF, PROPOSAL, WORKS, apiError, callsTo, findErrorAlert, mockBff, never, page, renderApp, seedActor } from '../test/helpers';

const detailRoutes = (proposal: object = PROPOSAL) => [
  { path: '/proposals/proposal_1', reply: proposal },
  { path: '/proposals/proposal_1/diff', reply: DIFF },
];

describe('提案列表', () => {
  it('loading', async () => {
    mockBff([{ path: '/works', reply: page(WORKS) }, { path: '/proposals', reply: never }]);
    renderApp('#/proposals');
    expect(await screen.findByText('正在加载提案…')).toBeInTheDocument();
  });

  it('empty', async () => {
    mockBff([{ path: '/works', reply: page(WORKS) }, { path: '/proposals', reply: page([]) }]);
    renderApp('#/proposals');
    expect(await screen.findByText('还没有提案')).toBeInTheDocument();
  });

  it('error 带重试', async () => {
    let n = 0;
    mockBff([
      { path: '/works', reply: page(WORKS) },
      { path: '/proposals', reply: () => (++n === 1 ? apiError(503, 'WORKER_UNAVAILABLE', '后端不可用') : page([PROPOSAL])) },
    ]);
    renderApp('#/proposals');
    await userEvent.click(within(await findErrorAlert()).getByRole('button', { name: '重试' }));
    const link = await screen.findByRole('link', { name: 'proposal_1' });
    expect(link).toHaveAttribute('href', '#/proposals/proposal_1');
  });

  it('按状态过滤时把取值传给服务端', async () => {
    const spy = mockBff([{ path: '/works', reply: page(WORKS) }, { path: '/proposals', reply: page([PROPOSAL]) }]);
    renderApp('#/proposals');
    await screen.findByRole('link', { name: 'proposal_1' });
    await userEvent.selectOptions(screen.getByLabelText('状态'), 'APPROVED');
    await waitFor(() => expect(callsTo(spy, 'GET', '/proposals').at(-1)?.url.searchParams.get('status')).toBe('APPROVED'));
  });
});

describe('提案审核页', () => {
  it('结构化 diff:label 徽标、可执行标记、before/after、风险', async () => {
    mockBff(detailRoutes());
    renderApp('#/proposals/proposal_1');
    expect(await screen.findByText('【演绎】杜甫望着城墙叹气。')).toBeInTheDocument();
    expect(screen.getAllByText('可执行 · 批准后写入草稿')).toHaveLength(2);
    expect(screen.getAllByText('仅留存 · 不会写入内容')).toHaveLength(2);
    expect(screen.getByText('来源请求', { selector: '.badge' })).toBeInTheDocument();
    expect(screen.getByText('演绎', { selector: '.badge' })).toBeInTheDocument();
    expect(screen.getByText('无出处')).toBeInTheDocument();
    expect(screen.getByText('城春草木深')).toBeInTheDocument();
  });

  it('可执行项没有逐项决定时,整体批准被挡住且可读到原因;决定后放开', async () => {
    mockBff(detailRoutes());
    renderApp('#/proposals/proposal_1');
    const approve = await screen.findByRole('button', { name: /整体批准/ });
    expect(approve).toHaveAttribute('aria-disabled', 'true');
    expect(approve).toHaveAccessibleDescription(/还有 2 个可执行项没有逐项决定/);

    const group0 = screen.getByRole('group', { name: /第 0 项的决定/ });
    const group1 = screen.getByRole('group', { name: /第 1 项的决定/ });
    await userEvent.click(within(group0).getByRole('radio', { name: /批准此项/ }));
    expect(approve).toHaveAttribute('aria-disabled', 'true');
    await userEvent.click(within(group1).getByRole('radio', { name: /驳回此项/ }));
    expect(approve).not.toHaveAttribute('aria-disabled');
    expect(screen.getByText(/已逐项决定 2 个/)).toBeInTheDocument();
  });

  it('被挡住时点击整体批准不会打开对话框', async () => {
    mockBff(detailRoutes());
    renderApp('#/proposals/proposal_1');
    await userEvent.click(await screen.findByRole('button', { name: /整体批准/ }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('非可执行项不要求逐项决定', async () => {
    mockBff(detailRoutes());
    renderApp('#/proposals/proposal_1');
    await screen.findByText('【演绎】杜甫望着城墙叹气。');
    expect(screen.queryByRole('group', { name: /第 2 项的决定/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('group', { name: /第 3 项的决定/ })).not.toBeInTheDocument();
  });

  it('角色不允许评审时:逐项与整体都禁用,并说明原因', async () => {
    seedActor('PLATFORM_ADMIN');
    mockBff(detailRoutes());
    renderApp('#/proposals/proposal_1');
    const group0 = await screen.findByRole('group', { name: /第 0 项的决定/ });
    expect(group0).toBeDisabled();
    expect(screen.getByRole('button', { name: /整体驳回/ })).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getAllByText(/当前角色 PLATFORM_ADMIN 不能评审提案/).length).toBeGreaterThan(0);
  });

  it('批准:提交带 actor 与全部逐项决定;文案说明不是发布', async () => {
    const spy = mockBff([
      ...detailRoutes(),
      { method: 'POST', path: '/proposals/proposal_1/review', reply: { ...PROPOSAL, status: 'APPROVED' } },
    ]);
    renderApp('#/proposals/proposal_1');
    await screen.findByRole('button', { name: /整体批准/ });
    await userEvent.click(within(screen.getByRole('group', { name: /第 0 项的决定/ })).getByRole('radio', { name: /批准此项/ }));
    await userEvent.click(within(screen.getByRole('group', { name: /第 1 项的决定/ })).getByRole('radio', { name: /批准此项/ }));
    await userEvent.click(screen.getByRole('button', { name: /整体批准/ }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('不会发布');
    await userEvent.click(within(dialog).getByRole('button', { name: '确认批准' }));
    await waitFor(() => expect(callsTo(spy, 'POST', '/review')).toHaveLength(1));
    expect(callsTo(spy, 'POST', '/review')[0]?.body).toMatchObject({
      decision: 'APPROVE',
      actor: { actor_id: 'studio-editor', role: 'CONTENT_EDITOR' },
      item_decisions: [
        { item_index: 0, decision: 'APPROVE' },
        { item_index: 1, decision: 'APPROVE' },
      ],
    });
  });

  it('整体驳回必须写评语', async () => {
    const spy = mockBff(detailRoutes());
    renderApp('#/proposals/proposal_1');
    await userEvent.click(await screen.findByRole('button', { name: /整体驳回/ }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: '确认驳回' }));
    expect(within(dialog).getByText('驳回必须写评语,说明原因。')).toBeInTheDocument();
    expect(callsTo(spy, 'POST', '/review')).toHaveLength(0);
  });

  it('对话框:焦点陷阱 + Esc 关闭并还原焦点', async () => {
    mockBff(detailRoutes());
    renderApp('#/proposals/proposal_1');
    const reject = await screen.findByRole('button', { name: /整体驳回/ });
    await userEvent.click(reject);
    const dialog = await screen.findByRole('dialog');
    for (let i = 0; i < 6; i += 1) {
      await userEvent.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(reject).toHaveFocus();
  });

  it('服务端 ITEM_DECISIONS_REQUIRED 会指出缺失项', async () => {
    mockBff([
      ...detailRoutes(),
      {
        method: 'POST',
        path: '/proposals/proposal_1/review',
        reply: apiError(422, 'ITEM_DECISIONS_REQUIRED', '缺少逐项决定', { missing_item_index: [1] }),
      },
    ]);
    renderApp('#/proposals/proposal_1');
    await userEvent.click(await screen.findByRole('button', { name: /整体驳回/ }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(within(dialog).getByLabelText(/评语/), '不采用');
    await userEvent.click(within(dialog).getByRole('button', { name: '确认驳回' }));
    expect(await within(dialog).findByText(/第 1 项/)).toBeInTheDocument();
  });

  it('已批准:按钮文案明确“写入草稿(不是发布)”,请求带 actor', async () => {
    const approved = { ...PROPOSAL, status: 'APPROVED', approved_executable_count: 1 };
    const spy = mockBff([...detailRoutes(approved), { method: 'POST', path: '/proposals/proposal_1/apply', reply: {} }]);
    renderApp('#/proposals/proposal_1');
    await userEvent.click(await screen.findByRole('button', { name: '写入草稿(不是发布)' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: '写入草稿(不是发布)' }));
    await waitFor(() => expect(callsTo(spy, 'POST', '/apply')).toHaveLength(1));
    expect(callsTo(spy, 'POST', '/apply')[0]?.body).toEqual({ actor: { actor_id: 'studio-editor', role: 'CONTENT_EDITOR' } });
  });

  it('已批准但没有被批准的可执行项:提示 NOTHING_TO_APPLY,不给应用按钮', async () => {
    mockBff(detailRoutes({ ...PROPOSAL, status: 'APPROVED', approved_executable_count: 0 }));
    renderApp('#/proposals/proposal_1');
    expect(await screen.findByText(/NOTHING_TO_APPLY/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '写入草稿(不是发布)' })).not.toBeInTheDocument();
  });

  it('服务端返回 409 NOTHING_TO_APPLY 时按提示处理,而不是报错', async () => {
    mockBff([
      ...detailRoutes({ ...PROPOSAL, status: 'APPROVED', approved_executable_count: 1 }),
      { method: 'POST', path: '/proposals/proposal_1/apply', reply: apiError(409, 'NOTHING_TO_APPLY', '无可应用项') },
    ]);
    renderApp('#/proposals/proposal_1');
    await userEvent.click(await screen.findByRole('button', { name: '写入草稿(不是发布)' }));
    await userEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '写入草稿(不是发布)' }));
    expect(await screen.findByText(/编辑记录留存/)).toBeInTheDocument();
    // The announcer is always in the DOM as role="alert" (sr-only, empty), so "no alert anywhere"
    // can never be true. What the case needs to prove is that no *error* was shown.
    expect(document.querySelector(".state--error, .notice--error, .boundary")).toBeNull();
  });

  it('PLATFORM_ADMIN 不能应用,说明原因', async () => {
    seedActor('PLATFORM_ADMIN');
    mockBff(detailRoutes({ ...PROPOSAL, status: 'APPROVED', approved_executable_count: 1 }));
    renderApp('#/proposals/proposal_1');
    const apply = await screen.findByRole('button', { name: '写入草稿(不是发布)' });
    expect(apply).toHaveAttribute('aria-disabled', 'true');
    expect(apply).toHaveAccessibleDescription(/不能写入草稿/);
  });

  it('loading 与 error', async () => {
    mockBff([{ path: '/proposals/proposal_1', reply: never }, { path: '/proposals/proposal_1/diff', reply: never }]);
    renderApp('#/proposals/proposal_1');
    expect(await screen.findByText('正在加载提案与 diff…')).toBeInTheDocument();
  });
});
