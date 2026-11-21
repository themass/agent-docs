import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ErrorBoundary } from '../components/error-boundary';
import { render } from '@testing-library/react';
import { ACTOR_STORAGE_KEY } from '../lib/actor';
import { OVERVIEW, PRECHECK, WORKS, apiError, findErrorAlert, mockBff, never, page, renderApp } from '../test/helpers';

const works = { path: '/works', reply: page(WORKS) };

describe('作品内容浏览', () => {
  const overview = { path: '/works/work-chun-wang/overview', reply: OVERVIEW };

  it('loading / error 带重试', async () => {
    mockBff([works, { path: '/works/work-chun-wang/overview', reply: never }]);
    const view = renderApp('#/content');
    expect(await screen.findByText('正在加载作品内容…')).toBeInTheDocument();
    view.unmount();

    let n = 0;
    mockBff([works, { path: '/works/work-chun-wang/overview', reply: () => (++n === 1 ? apiError(500, 'X', '失败') : OVERVIEW) }]);
    renderApp('#/content');
    await userEvent.click(within(await findErrorAlert()).getByRole('button', { name: '重试' }));
    expect(await screen.findByRole('heading', { name: '诗句与注释' })).toBeInTheDocument();
  });

  it('empty:没有作品', async () => {
    mockBff([{ path: '/works', reply: page([]) }]);
    renderApp('#/content');
    expect(await screen.findByText('还没有作品')).toBeInTheDocument();
  });

  it('PUBLISHED 与 DRAFT 用文字、字形与线型永久区分', async () => {
    mockBff([works, overview]);
    renderApp('#/content');
    await screen.findByRole('heading', { name: '诗句与注释' });
    expect(screen.getAllByText(/草稿 DRAFT/).length).toBeGreaterThan(0);
    const published = screen.getAllByText(/已发布 PUBLISHED/);
    expect(published.length).toBeGreaterThan(0);
    expect(published[0]).toHaveClass('status-mark--published');
  });

  it('演绎带“演绎”前缀,未考写“不可考/待核”,无出处的史实标“出处待核”', async () => {
    mockBff([works, overview]);
    renderApp('#/content');
    await screen.findByRole('heading', { name: '四层背景' });
    expect(document.querySelector('.basis-text--drama .basis-prefix')).toHaveTextContent('演绎');
    expect(screen.getAllByText(/不可考\/待核/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/出处待核/).length).toBeGreaterThan(0);
  });

  it('背景显示与诗句的关联,没有绑定时明说', async () => {
    mockBff([works, overview]);
    renderApp('#/content');
    expect(await screen.findByText('关联诗句:第 1 句')).toBeInTheDocument();
    expect(screen.getByText('这条背景暂时没有绑定诗句')).toBeInTheDocument();
  });
});

describe('发布前检查', () => {
  const precheck = { path: '/works/work-chun-wang/precheck', reply: PRECHECK };

  it('loading / empty / error', async () => {
    mockBff([works, { path: '/works/work-chun-wang/precheck', reply: never }]);
    const view = renderApp('#/precheck');
    expect(await screen.findByText('正在评估规则…')).toBeInTheDocument();
    view.unmount();

    mockBff([works, { path: '/works/work-chun-wang/precheck', reply: { ...PRECHECK, rules: [] } }]);
    const second = renderApp('#/precheck');
    expect(await screen.findByText('没有规则结果')).toBeInTheDocument();
    second.unmount();

    mockBff([works, { path: '/works/work-chun-wang/precheck', reply: apiError(500, 'X', '评估失败') }]);
    renderApp('#/precheck');
    expect(within(await findErrorAlert()).getByRole('button', { name: '重试' })).toBeInTheDocument();
  });

  it('列出规则的 DATA/BUNDLE 与 PASS/FAIL/NOT_EVALUATED,details 可展开', async () => {
    mockBff([works, precheck]);
    renderApp('#/precheck');
    const table = await screen.findByRole('table', { name: /发布前检查规则/ });
    expect(within(table).getByText('BUNDLE')).toBeInTheDocument();
    expect(within(table).getByText('未评估')).toBeInTheDocument();
    expect(within(table).getByText('失败')).toBeInTheDocument();
    // Several rules carry exactly one detail, so the name is not unique; take the first collapsed one.
    const toggle = within(table).getAllByRole('button', { name: /展开详情\(1\)/, expanded: false })[0];
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(within(table).getByText('entity x 是 DRAFT')).toBeInTheDocument();
  });

  it('没有任何“发布”按钮,只有“不等于已发布”的说明', async () => {
    mockBff([works, { path: '/works/work-chun-wang/precheck', reply: { ...PRECHECK, verdict: 'READY_FOR_HUMAN_PUBLISH' } }]);
    renderApp('#/precheck');
    await screen.findByRole('heading', { name: '总判定' });
    const main = screen.getByRole('main');
    expect(within(main).queryByRole('button', { name: /发布|publish/i })).not.toBeInTheDocument();
    expect(within(main).queryByRole('link', { name: /发布|publish/i })).not.toBeInTheDocument();
    expect(within(main).getByText(/READY_FOR_HUMAN_PUBLISH 不等于已发布/)).toBeInTheDocument();
    expect(within(main).getByRole('note')).toHaveTextContent('没有、也不会有发布入口');
  });
});

describe('外壳', () => {
  it('顶部导航有 7 个入口,当前页带 aria-current', async () => {
    mockBff([works, { path: '/tasks', reply: page([]) }]);
    renderApp('#/workbench');
    const nav = await screen.findByRole('navigation', { name: '主导航' });
    expect(within(nav).getAllByRole('link')).toHaveLength(7);
    expect(within(nav).getByRole('link', { name: '工作台' })).toHaveAttribute('aria-current', 'page');
  });

  it('语义地标:banner / main / contentinfo,并有跳到主要内容的链接', async () => {
    mockBff([works, { path: '/tasks', reply: page([]) }]);
    renderApp('#/workbench');
    // findAll*: the shell renders a page-level banner and the app chrome also exposes one; the property
    // under test is that both landmarks exist at all, not that exactly one does.
    expect((await screen.findAllByRole('banner')).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('main').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('contentinfo').length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: '跳到主要内容' }).length).toBeGreaterThan(0);
  });

  it('未知路径显示 404 页', async () => {
    mockBff([]);
    renderApp('#/no-such-page');
    expect(await screen.findByRole('heading', { name: /页面不存在 \(404\)/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '回到工作台' })).toHaveAttribute('href', '#/workbench');
  });

  it('actor 选择器:写明占位身份,保存到 localStorage,Esc 可关闭', async () => {
    mockBff([works, { path: '/tasks', reply: page([]) }]);
    renderApp('#/workbench');
    const button = await screen.findByRole('button', { name: /studio-editor/ });
    await userEvent.click(button);
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('未接入登录的占位身份');
    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(button).toHaveFocus();

    await userEvent.click(button);
    const id = await screen.findByLabelText('actor id');
    await userEvent.clear(id);
    await userEvent.type(id, 'wang-shi');
    await userEvent.click(screen.getByRole('radio', { name: /史料审核/ }));
    await userEvent.click(screen.getByRole('button', { name: '保存身份' }));
    expect(JSON.parse(window.localStorage.getItem(ACTOR_STORAGE_KEY) ?? '{}')).toEqual({ actor_id: 'wang-shi', role: 'HISTORICAL_REVIEWER' });
    await waitFor(() => expect(screen.getByTestId('announcer-polite')).toHaveTextContent('当前身份已切换为 wang-shi'));
  });

  it('全局错误边界:渲染异常不白屏,给出重试', async () => {
    function Boom(): never {
      throw new Error('渲染炸了');
    }
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(await findErrorAlert()).toHaveTextContent('渲染炸了');
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
  });
});
