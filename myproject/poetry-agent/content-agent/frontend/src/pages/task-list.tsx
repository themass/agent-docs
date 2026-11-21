import { listTasks, listWorks } from '../api/client';
import { TASK_TYPES, type WorkSummary } from '../api/types';
import { AsyncView, EmptyView } from '../components/async-view';
import { Button, Pager, RunStatusChip } from '../components/ui';
import { formatTime } from '../lib/format';
import { TASK_TYPE_INFO, taskTypeLabel } from '../lib/labels';
import { useQueryUpdater, useRoute } from '../lib/router';
import { useAsync } from '../lib/use-async';

export const PAGE_SIZE = 20;
const STATUS_OPTIONS = ['CREATED', 'RUNNING', 'WAITING_FOR_RUNTIME', 'AWAITING_REVIEW', 'COMPLETED', 'FAILED'];

/** 任务列表:筛选(作品/状态/类型)与分页都存在 URL 查询里,刷新与回退不丢上下文。 */
export function TaskList({ works }: { works: WorkSummary[] }) {
  const { query } = useRoute();
  const update = useQueryUpdater();
  const work = query.work ?? '';
  const status = query.status ?? '';
  const type = query.type ?? '';
  const offset = Number(query.offset ?? '0') || 0;
  const filtered = work !== '' || status !== '' || type !== '';

  const result = useAsync(
    signal =>
      listTasks(
        { work_id: work, status, task_type: type, limit: PAGE_SIZE, offset },
        signal,
      ),
    [work, status, type, offset],
  );
  const workTitle = (id: string) => works.find(w => w.work_id === id)?.title ?? id;

  return (
    <section aria-labelledby="task-list-title">
      <h2 id="task-list-title">任务列表</h2>
      <form className="filters" role="search" aria-label="筛选任务" onSubmit={event => event.preventDefault()}>
        <div className="filters__item">
          <label htmlFor="f-work">作品</label>
          <select id="f-work" value={work} onChange={e => update({ work: e.target.value || undefined, offset: undefined })}>
            <option value="">全部作品</option>
            {works.map(w => (
              <option key={w.work_id} value={w.work_id}>
                {w.title}
              </option>
            ))}
          </select>
        </div>
        <div className="filters__item">
          <label htmlFor="f-status">状态</label>
          <select id="f-status" value={status} onChange={e => update({ status: e.target.value || undefined, offset: undefined })}>
            <option value="">全部状态</option>
            {STATUS_OPTIONS.map(s => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="filters__item">
          <label htmlFor="f-type">类型</label>
          <select id="f-type" value={type} onChange={e => update({ type: e.target.value || undefined, offset: undefined })}>
            <option value="">全部类型</option>
            {TASK_TYPES.map(t => (
              <option key={t} value={t}>
                {TASK_TYPE_INFO[t].label}
              </option>
            ))}
          </select>
        </div>
        {filtered ? (
          <Button variant="quiet" onClick={() => update({ work: undefined, status: undefined, type: undefined, offset: undefined })}>
            清除筛选
          </Button>
        ) : null}
      </form>

      <AsyncView
        result={result}
        loadingLabel="正在加载任务…"
        errorTitle="任务列表加载失败"
        empty={page =>
          page.items.length === 0 ? (
            <EmptyView title={filtered ? '没有符合筛选条件的任务' : '还没有任务'}>
              {filtered ? '换一个筛选条件,或清除筛选。' : '在右侧创建第一个任务。'}
            </EmptyView>
          ) : null
        }
      >
        {page => (
          <>
            <table className="table">
              <caption className="sr-only">任务列表,按创建时间倒序</caption>
              <thead>
                <tr>
                  <th scope="col">任务</th>
                  <th scope="col">作品</th>
                  <th scope="col">类型</th>
                  <th scope="col">状态</th>
                  <th scope="col">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map(task => (
                  <tr key={task.task_id}>
                    <th scope="row">
                      <a href={`#/tasks/${encodeURIComponent(task.task_id)}`}>{task.title}</a>
                    </th>
                    <td>{workTitle(task.work_id)}</td>
                    <td>{taskTypeLabel(task.task_type)}</td>
                    <td>
                      <RunStatusChip status={task.status} />
                    </td>
                    <td className="num">{formatTime(task.created_at)}</td>
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
    </section>
  );
}

/** 供页面按需加载作品列表(仅取 items)。 */
export function useWorkList() {
  return useAsync(async signal => (await listWorks(signal)).items, []);
}
