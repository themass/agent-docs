import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { COVERAGE, GAP_REPORT, SOURCES, WORKS, apiError, callsTo, findErrorAlert, mockBff, never, page, renderApp, seedActor } from '../test/helpers';

const works = { path: '/works', reply: page(WORKS) };

describe('缺口与覆盖看板', () => {
  it('loading', async () => {
    mockBff([works, { path: '/works/work-chun-wang/coverage', reply: never }, { path: '/works/work-chun-wang/gap-report', reply: never }]);
    renderApp('#/coverage');
    expect(await screen.findByText('正在加载覆盖数据…')).toBeInTheDocument();
  });

  it('error 带重试', async () => {
    let n = 0;
    mockBff([
      works,
      { path: '/works/work-chun-wang/coverage', reply: () => (++n === 1 ? apiError(500, 'INTERNAL', '覆盖计算失败') : COVERAGE) },
      { path: '/works/work-chun-wang/gap-report', reply: GAP_REPORT },
    ]);
    renderApp('#/coverage');
    await userEvent.click(within(await findErrorAlert()).getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('heading', { name: '总量' })).toBeInTheDocument();
  });

  it('empty:作品没有诗句', async () => {
    mockBff([
      works,
      { path: '/works/work-chun-wang/coverage', reply: { ...COVERAGE, lines: [], gap_codes: [] } },
      { path: '/works/work-chun-wang/gap-report', reply: { gaps: [] } },
    ]);
    renderApp('#/coverage');
    expect(await screen.findByText('这个作品还没有诗句')).toBeInTheDocument();
    expect(screen.getByText('没有缺口代码')).toBeInTheDocument();
  });

  it('数字加条形的表格视图,以及逐句缺口用文字标出', async () => {
    mockBff([
      works,
      { path: '/works/work-chun-wang/coverage', reply: COVERAGE },
      { path: '/works/work-chun-wang/gap-report', reply: GAP_REPORT },
    ]);
    renderApp('#/coverage');
    const table = await screen.findByRole('table', { name: 'claim 按状态' });
    expect(within(table).getByRole('row', { name: /DRAFT/ })).toHaveTextContent('3');
    expect(within(table).getByRole('row', { name: /DRAFT/ })).toHaveTextContent('100%');
    const matrix = screen.getByRole('table', { name: /逐句覆盖矩阵/ });
    const row2 = within(matrix).getByRole('row', { name: /城春草木深/ });
    expect(row2).toHaveTextContent('无注释');
    expect(row2).toHaveTextContent('无背景');
    expect(screen.getByRole('meter', { name: /可核查 claim/ })).toHaveAttribute('aria-valuenow', '0');
    expect(await screen.findByText('3 条 claim 没有已核验引用')).toBeInTheDocument();
  });

  it('只看有缺口的句子', async () => {
    mockBff([
      works,
      { path: '/works/work-chun-wang/coverage', reply: COVERAGE },
      { path: '/works/work-chun-wang/gap-report', reply: GAP_REPORT },
    ]);
    renderApp('#/coverage');
    await screen.findByRole('table', { name: /逐句覆盖矩阵/ });
    await userEvent.click(screen.getByRole('checkbox', { name: /只看有缺口的句子/ }));
    expect(screen.queryByText('国破山河在', { selector: 'th' })).not.toBeInTheDocument();
    expect(screen.getByText('城春草木深', { selector: 'th' })).toBeInTheDocument();
  });
});

describe('出处核查工作台', () => {
  const sourcesRoute = { path: '/sources', reply: page(SOURCES) };

  it('顶部固定提示 agent 没有此权限', async () => {
    mockBff([sourcesRoute]);
    renderApp('#/sources');
    expect(await screen.findByRole('note')).toHaveTextContent('agent 没有此权限');
  });

  it('loading / empty / error', async () => {
    mockBff([{ path: '/sources', reply: never }]);
    const view = renderApp('#/sources');
    expect(await screen.findByText('正在加载来源…')).toBeInTheDocument();
    view.unmount();

    mockBff([{ path: '/sources', reply: page([]) }]);
    renderApp('#/sources');
    expect(await screen.findByText('没有待核验的来源')).toBeInTheDocument();
  });

  it('error 带重试', async () => {
    let n = 0;
    mockBff([{ path: '/sources', reply: () => (++n === 1 ? apiError(503, 'STUDIO_UNAVAILABLE', '读通道未配置') : page(SOURCES)) }]);
    renderApp('#/sources');
    await userEvent.click(within(await findErrorAlert()).getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('link', { name: /旧唐书/ })).toBeInTheDocument();
  });

  it('来源列表显示支撑的 claim 数与 locator 未就绪数,项目是链接(可回车进入)', async () => {
    mockBff([sourcesRoute]);
    renderApp('#/sources');
    const link = await screen.findByRole('link', { name: /旧唐书/ });
    expect(link).toHaveTextContent('支撑 2 条 claim · 1 条 locator 未就绪');
    expect(link).toHaveAttribute('href', expect.stringContaining('source=src-a'));
  });

  it('有非 SET 的 locator 时 VERIFY 禁用,并列出缺项', async () => {
    seedActor('HISTORICAL_REVIEWER');
    mockBff([sourcesRoute]);
    renderApp('#/sources?source=src-a');
    const verify = await screen.findByRole('button', { name: /核验 VERIFY/ });
    expect(verify).toHaveAttribute('aria-disabled', 'true');
    expect(verify).toHaveAccessibleDescription(/claim-a1 的 locator 状态是 MISSING/);
  });

  it('全部 SET 且角色、署名合规时 VERIFY 可用', async () => {
    seedActor('HISTORICAL_REVIEWER');
    mockBff([sourcesRoute]);
    renderApp('#/sources?source=src-b');
    expect(await screen.findByRole('button', { name: /核验 VERIFY/ })).not.toHaveAttribute('aria-disabled');
  });

  it('角色不足:输入被禁用并说明原因(服务端为准)', async () => {
    seedActor('CONTENT_EDITOR');
    mockBff([sourcesRoute]);
    renderApp('#/sources?source=src-b');
    // Shown both as a page notice and inline next to the disabled field; either is fine, so count them.
    expect((await screen.findAllByText(/当前角色 CONTENT_EDITOR 不能填写 locator 或核验来源/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /核验 VERIFY/ })).toHaveAttribute('aria-disabled', 'true');
  });

  it('署名不能像 agent:字段报错并与输入关联', async () => {
    seedActor('HISTORICAL_REVIEWER');
    mockBff([sourcesRoute]);
    renderApp('#/sources?source=src-b');
    const input = await screen.findByLabelText('署名(审核人姓名)');
    await userEvent.clear(input);
    await userEvent.type(input, 'ai-reviewer');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription(/不能像 agent/);
    expect(screen.getByRole('button', { name: /核验 VERIFY/ })).toHaveAttribute('aria-disabled', 'true');
  });

  it('保存 locator:占位词在前端被挡住,不发请求', async () => {
    seedActor('HISTORICAL_REVIEWER');
    const spy = mockBff([sourcesRoute]);
    renderApp('#/sources?source=src-a');
    const input = await screen.findByLabelText('locator(卷/页/篇名)', { selector: '#cit-claim-a1-locator' });
    await userEvent.type(input, '待核查');
    await userEvent.click(screen.getAllByRole('button', { name: '保存 locator' })[0]!);
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(callsTo(spy, 'PUT', '/locator')).toHaveLength(0);
  });

  it('保存 locator 成功:PUT 带署名与角色,随后刷新列表', async () => {
    seedActor('HISTORICAL_REVIEWER');
    const spy = mockBff([sourcesRoute, { method: 'PUT', path: '/sources/citations/claim-a1/src-a/locator', reply: {} }]);
    renderApp('#/sources?source=src-a');
    const input = await screen.findByLabelText('locator(卷/页/篇名)', { selector: '#cit-claim-a1-locator' });
    await userEvent.type(input, '卷九·玄宗纪');
    const before = callsTo(spy, 'GET', '/sources').length;
    await userEvent.click(screen.getAllByRole('button', { name: '保存 locator' })[0]!);
    await waitFor(() => expect(callsTo(spy, 'PUT', '/locator')).toHaveLength(1));
    expect(callsTo(spy, 'PUT', '/locator')[0]?.body).toMatchObject({
      locator: '卷九·玄宗纪',
      actor: { actor_id: 'li-wen', role: 'HISTORICAL_REVIEWER' },
    });
    await waitFor(() => expect(callsTo(spy, 'GET', '/sources').length).toBeGreaterThan(before));
  });

  it('核验 409 STUDIO_CONFLICT:显示服务端列出的缺失项', async () => {
    seedActor('HISTORICAL_REVIEWER');
    mockBff([
      sourcesRoute,
      { method: 'POST', path: '/sources/src-b/verification', reply: apiError(409, 'STUDIO_CONFLICT', '存在缺失 locator', { missing: ['claim-b9'] }) },
    ]);
    renderApp('#/sources?source=src-b');
    await userEvent.click(await screen.findByRole('button', { name: /核验 VERIFY/ }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: '确认核验' }));
    expect(await within(dialog).findByText(/claim-b9/)).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});
