import { useState } from 'react';
import { getTask, listRuns, startRun } from '../api/client';
import type { AgentRun, AgentTask } from '../api/types';
import { useAnnounce } from '../components/announcer';
import { AsyncView, EmptyView } from '../components/async-view';
import { ErrorDetails } from '../components/error-details';
import { Button, PageHeader, RunStatusChip } from '../components/ui';
import { describeError, detailOf, errorCode } from '../lib/errors';
import { formatTime } from '../lib/format';
import { taskTypeLabel } from '../lib/labels';
import { navigate, useRoute } from '../lib/router';
import { useAsync } from '../lib/use-async';
import { isActive } from '../lib/use-run-observation';
import type { ObservationOptions } from '../lib/use-run-observation';
import { RunObservatory } from './run-observatory';

interface StartFailure {
  message: string;
  code?: string;
  details?: unknown;
  runId?: string;
}

function TaskBody({
  task,
  runs,
  reload,
  observation,
}: {
  task: AgentTask;
  runs: AgentRun[];
  reload: () => void;
  observation?: Pick<ObservationOptions, 'stream' | 'idleCloseMs'>;
}) {
  const route = useRoute();
  const announce = useAnnounce();
  const [pending, setPending] = useState<'default' | 'stub' | null>(null);
  const [failure, setFailure] = useState<StartFailure | null>(null);

  const selected =
    runs.find(r => r.run_id === route.query.run) ?? runs.find(r => r.run_id === task.active_run_id) ?? runs[0];
  const hasActive = runs.some(r => isActive(r.status));
  const latest = runs[0];
  const canRetry = !hasActive && latest !== undefined && (latest.status === 'FAILED' || latest.status === 'COMPLETED');

  const start = async (runtime: 'STUB' | undefined) => {
    setPending(runtime ? 'stub' : 'default');
    setFailure(null);
    try {
      const run = await startRun(task.task_id, runtime);
      announce('运行已提交。');
      navigate(`/tasks/${encodeURIComponent(task.task_id)}`, { run: run.run_id }, true);
      reload();
    } catch (error) {
      const info = describeError(error);
      const code = errorCode(error);
      const runId = detailOf(error, 'run_id');
      setFailure({
        message: info.message,
        code,
        details: info.details,
        runId: typeof runId === 'string' ? runId : undefined,
      });
      announce(`运行未启动:${info.message}`, true);
      if (code === 'WORKER_UNAVAILABLE') reload();
    } finally {
      setPending(null);
    }
  };

  return (
    <>
      <section aria-labelledby="task-meta-title" className="panel">
        <h2 id="task-meta-title" className="sr-only">
          任务信息
        </h2>
        <dl className="meta-grid">
          <div>
            <dt>作品</dt>
            <dd>
              <code>{task.work_id}</code>
            </dd>
          </div>
          <div>
            <dt>类型</dt>
            <dd>{taskTypeLabel(task.task_type)}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>
              <RunStatusChip status={task.status} />
            </dd>
          </div>
          <div>
            <dt>创建</dt>
            <dd className="num">{formatTime(task.created_at)}</dd>
          </div>
          <div>
            <dt>创建人</dt>
            <dd>{task.actor ? `${task.actor.actor_id}(${task.actor.role})` : '—'}</dd>
          </div>
        </dl>
        <figure className="instructions">
          <figcaption>指令(不可信材料,agent 不会把它当命令执行)</figcaption>
          <blockquote>{task.instructions}</blockquote>
        </figure>

        <div className="actions">
          {runs.length === 0 ? (
            <Button variant="primary" blocked={pending !== null} onClick={() => void start(undefined)}>
              {pending === 'default' ? '正在提交…' : '开始运行'}
            </Button>
          ) : null}
          {canRetry ? (
            <>
              <Button variant="secondary" blocked={pending !== null} onClick={() => void start(undefined)}>
                {pending === 'default' ? '正在提交…' : '再次运行'}
              </Button>
              <Button variant="secondary" blocked={pending !== null} onClick={() => void start('STUB')}>
                {pending === 'stub' ? '正在提交…' : '用确定性运行时重试'}
              </Button>
            </>
          ) : null}
          {runs.length > 0 && !canRetry && !hasActive ? (
            <Button variant="secondary" blocked={pending !== null} onClick={() => void start('STUB')}>
              用确定性运行时重试
            </Button>
          ) : null}
        </div>
        <p className="field__hint">
          “确定性运行时”(STUB)不调用模型,基于 Java 快照做真实分析;模型运行失败时不会自动降级,需要你手动选择它。
        </p>

        {failure ? (
          <div className="notice notice--error" role="alert">
            <p>
              <span aria-hidden="true">✕ </span>
              {failure.message}
              {failure.code ? (
                <>
                  {' '}
                  <code>{failure.code}</code>
                </>
              ) : null}
            </p>
            {failure.code === 'RUN_ALREADY_ACTIVE' && failure.runId ? (
              <p>
                <a href={`#/tasks/${encodeURIComponent(task.task_id)}?run=${encodeURIComponent(failure.runId)}`}>查看正在运行的 {failure.runId}</a>
              </p>
            ) : null}
            {failure.code === 'TASK_NOT_RUNNABLE' ? (
              <p>
                <a href={`#/proposals?task=${encodeURIComponent(task.task_id)}`}>去处理该任务的待评审提案</a>
              </p>
            ) : null}
            {failure.code === 'WORKER_UNAVAILABLE' ? (
              <p>运行记录已创建但 worker 不可达,未开始执行。恢复 worker 后可重新运行。</p>
            ) : null}
            <ErrorDetails details={failure.details} />
          </div>
        ) : null}
      </section>

      <section aria-labelledby="runs-title">
        <h2 id="runs-title">运行</h2>
        {runs.length === 0 ? (
          <EmptyView title="这个任务还没有运行">点击“开始运行”提交。运行由独立的 worker 执行,这里会实时显示进度。</EmptyView>
        ) : (
          <>
            <nav aria-label="运行列表">
              <ul className="run-tabs">
                {runs.map(run => (
                  <li key={run.run_id}>
                    <a
                      href={`#/tasks/${encodeURIComponent(task.task_id)}?run=${encodeURIComponent(run.run_id)}`}
                      aria-current={selected?.run_id === run.run_id ? 'true' : undefined}
                    >
                      <RunStatusChip status={run.status} /> <code>{run.run_id}</code>
                      <span className="run-tabs__sub">
                        {run.runtime} · {formatTime(run.created_at)}
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </nav>
            {selected ? <RunObservatory key={selected.run_id} initialRun={selected} options={observation} onRunChanged={reload} /> : null}
          </>
        )}
      </section>
    </>
  );
}

export function TaskDetailPage({
  taskId,
  observation,
}: {
  taskId: string;
  observation?: Pick<ObservationOptions, 'stream' | 'idleCloseMs'>;
}) {
  const result = useAsync(
    async signal => {
      const [task, runs] = await Promise.all([getTask(taskId, signal), listRuns(taskId, signal)]);
      return { task, runs };
    },
    [taskId],
  );
  return (
    <>
      <PageHeader
        title="任务详情与运行观测"
        lead={
          <>
            <a href="#/tasks">← 返回任务列表</a>
          </>
        }
      />
      <AsyncView result={result} loadingLabel="正在加载任务…" errorTitle="任务加载失败">
        {data => (
          <>
            <h2 className="task-title">{data.task.title}</h2>
            <TaskBody task={data.task} runs={data.runs} reload={result.refresh} observation={observation} />
          </>
        )}
      </AsyncView>
    </>
  );
}
