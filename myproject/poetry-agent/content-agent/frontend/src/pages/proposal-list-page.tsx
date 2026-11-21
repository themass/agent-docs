import { listProposals } from '../api/client';
import { AsyncView, EmptyView } from '../components/async-view';
import { Button, PageHeader, Pager, ProposalStatusChip } from '../components/ui';
import { formatTime, truncate } from '../lib/format';
import { useQueryUpdater, useRoute } from '../lib/router';
import { useAsync } from '../lib/use-async';
import { useWorkList } from './task-list';

const PAGE_SIZE = 20;
// 取值来自 BFF 实际行为:GET /proposals?status=REVIEW_REQUIRED|APPROVED|REJECTED|APPLIED。
const STATUS_OPTIONS: [string, string][] = [
  ['REVIEW_REQUIRED', '待评审'],
  ['APPROVED', '已批准'],
  ['REJECTED', '已驳回'],
  ['APPLIED', '已写入草稿'],
];

export function ProposalListPage() {
  const { query } = useRoute();
  const update = useQueryUpdater();
  const works = useWorkList();
  const work = query.work ?? '';
  const status = query.status ?? '';
  const task = query.task ?? '';
  const run = query.run ?? '';
  const offset = Number(query.offset ?? '0') || 0;
  const filtered = work !== '' || status !== '' || task !== '' || run !== '';

  const result = useAsync(
    signal => listProposals({ work_id: work, status, task_id: task, run_id: run, limit: PAGE_SIZE, offset }, signal),
    [work, status, task, run, offset],
  );
  const workItems = works.state.status === 'ready' ? works.state.data : [];
  const workTitle = (id: string) => workItems.find(w => w.work_id === id)?.title ?? id;

  return (
    <>
      <PageHeader title="提案审核" lead="agent 的候选改动先在这里审核。批准只允许写入 DRAFT,不会发布。" />
      <form className="filters" role="search" aria-label="筛选提案" onSubmit={event => event.preventDefault()}>
        <div className="filters__item">
          <label htmlFor="pf-work">作品</label>
          <select id="pf-work" value={work} onChange={e => update({ work: e.target.value || undefined, offset: undefined })}>
            <option value="">全部作品</option>
            {workItems.map(w => (
              <option key={w.work_id} value={w.work_id}>
                {w.title}
              </option>
            ))}
          </select>
        </div>
        <div className="filters__item">
          <label htmlFor="pf-status">状态</label>
          <select id="pf-status" value={status} onChange={e => update({ status: e.target.value || undefined, offset: undefined })}>
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}({value})
              </option>
            ))}
          </select>
        </div>
        {task ? (
          <div className="filters__item filters__chip">
            任务 <code>{task}</code>
            <Button variant="quiet" aria-label="移除任务筛选" onClick={() => update({ task: undefined, offset: undefined })}>
              ✕
            </Button>
          </div>
        ) : null}
        {run ? (
          <div className="filters__item filters__chip">
            运行 <code>{run}</code>
            <Button variant="quiet" aria-label="移除运行筛选" onClick={() => update({ run: undefined, offset: undefined })}>
              ✕
            </Button>
          </div>
        ) : null}
        {filtered ? (
          <Button variant="quiet" onClick={() => update({ work: undefined, status: undefined, task: undefined, run: undefined, offset: undefined })}>
            清除筛选
          </Button>
        ) : null}
      </form>

      <AsyncView
        result={result}
        loadingLabel="正在加载提案…"
        errorTitle="提案列表加载失败"
        empty={page =>
          page.items.length === 0 ? (
            <EmptyView title={filtered ? '没有符合筛选条件的提案' : '还没有提案'}>
              {filtered ? '换一个筛选条件,或清除筛选。' : '提案由 agent 运行成功并通过输出校验后产生。先到“工作台”创建并运行任务。'}
            </EmptyView>
          ) : null
        }
      >
        {page => (
          <>
            <table className="table">
              <caption className="sr-only">提案列表</caption>
              <thead>
                <tr>
                  <th scope="col">提案</th>
                  <th scope="col">作品</th>
                  <th scope="col">摘要</th>
                  <th scope="col">状态</th>
                  <th scope="col">可执行项</th>
                  <th scope="col">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map(proposal => (
                  <tr key={proposal.proposal_id}>
                    <th scope="row">
                      <a href={`#/proposals/${encodeURIComponent(proposal.proposal_id)}`}>{proposal.proposal_id}</a>
                    </th>
                    <td>{workTitle(proposal.work_id)}</td>
                    <td>{truncate(proposal.payload?.summary ?? '(无摘要)', 60)}</td>
                    <td>
                      <ProposalStatusChip status={proposal.status} />
                    </td>
                    <td className="num">{proposal.executable_count ?? '—'}</td>
                    <td className="num">{formatTime(proposal.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager
              offset={page.offset}
              limit={page.limit || PAGE_SIZE}
              count={page.items.length}
              hasMore={page.has_more}
              onChange={next => update({ offset: next === 0 ? undefined : String(next) })}
            />
          </>
        )}
      </AsyncView>
    </>
  );
}
