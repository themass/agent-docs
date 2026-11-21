import { useState } from 'react';
import { cancelRun, listProposals } from '../api/client';
import type { AgentRun, BudgetSummary, RunEvent } from '../api/types';
import { useAnnounce } from '../components/announcer';
import { AsyncView, EmptyView } from '../components/async-view';
import { Dialog } from '../components/dialog';
import { ErrorView } from '../components/async-view';
import { Button, Meter, ProposalStatusChip, RunStatusChip } from '../components/ui';
import { useActor } from '../lib/actor';
import { groupEvents, isFaultEvent, summarizePayload } from '../lib/event-view';
import { formatDuration, formatNumber, formatTime, truncate } from '../lib/format';
import { useAsync } from '../lib/use-async';
import { isActive, isTerminal, useRunObservation, type ObservationOptions } from '../lib/use-run-observation';
import type { StreamState } from '../api/events';

const STREAM_TEXT: Record<StreamState, string> = {
  connecting: '正在连接事件流…',
  open: '事件流已连接',
  reconnecting: '连接中断,正在重连并从上次的事件续传…',
  polling: '事件流不可用,已回退为定时刷新状态与预算(事件明细暂不更新)',
  closed: '事件流已关闭',
};

function BudgetPanel({ budget }: { budget: BudgetSummary | null }) {
  if (!budget) {
    return (
      <EmptyView title="暂无预算数据">
        运行尚未产生 BUDGET_UPDATE 事件。开始运行后这里会显示工具调用、耗时、token 与上限的对比。
      </EmptyView>
    );
  }
  return (
    <div className="meters">
      <Meter
        label="工具调用"
        value={budget.tool_calls}
        max={budget.max_tool_calls}
        valueText={`${formatNumber(budget.tool_calls)} / ${formatNumber(budget.max_tool_calls)} 次`}
      />
      <Meter
        label="耗时"
        value={budget.elapsed_s}
        max={budget.max_wall_s}
        valueText={`${formatDuration(budget.elapsed_s)} / ${formatDuration(budget.max_wall_s)}`}
      />
      <Meter
        label="Token"
        value={budget.tokens}
        max={budget.max_tokens}
        valueText={`${formatNumber(budget.tokens)} / ${formatNumber(budget.max_tokens)}`}
      />
    </div>
  );
}

function EventLog({ events }: { events: RunEvent[] }) {
  if (events.length === 0) {
    return <EmptyView title="还没有事件">事件会在运行产生后出现在这里。载荷只展示元数据,不显示提示词或模型原文。</EmptyView>;
  }
  return (
    <div className="event-groups">
      {groupEvents(events).map(({ group, events: items }) => (
        <details key={group.id} className="event-group" open>
          <summary>
            {group.label}
            <span className="event-group__count">{items.length}</span>
          </summary>
          <ol className="event-list">
            {items.map(event => {
              const summary = summarizePayload(event.payload);
              const fault = isFaultEvent(event.event_type);
              return (
                <li key={event.event_id} className={fault ? 'event event--fault' : 'event'}>
                  <span className="event__time num">{formatTime(event.occurred_at)}</span>
                  <span className="event__type">
                    {fault ? <span className="event__flag">故障 </span> : null}
                    <code>{event.event_type}</code>
                  </span>
                  <span className="event__meta">
                    {summary.text || '无元数据'}
                    {summary.hiddenCount > 0 ? `(已隐藏 ${summary.hiddenCount} 个疑似正文字段)` : ''}
                  </span>
                </li>
              );
            })}
          </ol>
        </details>
      ))}
    </div>
  );
}

function RunProposals({ run, refreshKey }: { run: AgentRun; refreshKey: number }) {
  const result = useAsync(signal => listProposals({ run_id: run.run_id, limit: 50 }, signal), [run.run_id, refreshKey, run.status]);
  return (
    <AsyncView
      result={result}
      loadingLabel="正在加载本次运行的提案…"
      errorTitle="提案加载失败"
      empty={page =>
        page.items.length === 0 ? (
          <EmptyView title="这次运行还没有生成提案">
            提案只由 worker 在输出校验通过后写入。若运行失败或校验被拒,这里会一直为空。
          </EmptyView>
        ) : null
      }
    >
      {page => (
        <ul className="plain-list">
          {page.items.map(proposal => (
            <li key={proposal.proposal_id} className="row">
              <a href={`#/proposals/${encodeURIComponent(proposal.proposal_id)}`}>{proposal.proposal_id}</a>
              <ProposalStatusChip status={proposal.status} />
              <span className="row__text">{truncate(proposal.payload?.summary ?? '(无摘要)', 80)}</span>
            </li>
          ))}
        </ul>
      )}
    </AsyncView>
  );
}

function CancelDialog({ run, onClose, onDone }: { run: AgentRun; onClose: () => void; onDone: () => void }) {
  const { bodyActor } = useActor();
  const announce = useAnnounce();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const confirm = async () => {
    setPending(true);
    setError(null);
    try {
      await cancelRun(run.run_id, bodyActor);
      announce('运行已取消。');
      onDone();
      onClose();
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog
      title="取消这次运行?"
      onClose={onClose}
      busy={pending}
      footer={
        <>
          <Button variant="quiet" onClick={onClose} blocked={pending}>
            不取消
          </Button>
          <Button variant="primary" onClick={() => void confirm()} blocked={pending} data-autofocus>
            {pending ? '正在取消…' : '确认取消'}
          </Button>
        </>
      }
    >
      <p>
        运行 <code>{run.run_id}</code> 会被终止。取消后状态显示为“失败”,原因记为“已由编辑取消”,之后可以用确定性运行时重试。
      </p>
      {error ? <ErrorView error={error} title="取消失败" /> : null}
    </Dialog>
  );
}

/** 单个运行的观测面板:状态条、预算、事件流、提案入口。 */
export function RunObservatory({
  initialRun,
  options,
  onRunChanged,
}: {
  initialRun: AgentRun;
  options?: Pick<ObservationOptions, 'stream' | 'idleCloseMs'>;
  onRunChanged: () => void;
}) {
  const [proposalKey, setProposalKey] = useState(0);
  const [cancelOpen, setCancelOpen] = useState(false);
  const announce = useAnnounce();
  const obs = useRunObservation(initialRun, {
    ...options,
    onStatusChange: next => {
      announce(`运行状态变为 ${next.status}`);
      onRunChanged();
    },
    onProposalEvent: () => setProposalKey(k => k + 1),
  });
  const { run } = obs;
  const terminal = isTerminal(run.status);

  return (
    <div className="observatory">
      <section className="statusbar" aria-label="运行状态">
        <div className="statusbar__main">
          <RunStatusChip status={run.status} />
          <span>
            运行时 <code>{run.runtime}</code>
          </span>
          <span className="num">创建 {formatTime(run.created_at)}</span>
          <span className="num">更新 {formatTime(run.updated_at)}</span>
        </div>
        <p className="statusbar__ids">
          run <code>{run.run_id}</code>
          {run.mandate_id ? (
            <>
              {' '}
              · mandate <code>{run.mandate_id}</code>
            </>
          ) : null}
        </p>
        {run.reason ? (
          <p className="notice notice--warn">
            <strong>原因:</strong>
            {run.reason}
          </p>
        ) : null}
        {terminal ? (
          <p className="statusbar__hint">运行已结束。事件流在没有新事件后会自动关闭。</p>
        ) : (
          <p className="statusbar__hint">运行尚未结束,状态会随事件自动更新。</p>
        )}
        {isActive(run.status) ? (
          <Button variant="secondary" onClick={() => setCancelOpen(true)}>
            取消运行
          </Button>
        ) : null}
      </section>

      <section aria-labelledby="budget-title">
        <h3 id="budget-title">预算消耗</h3>
        <BudgetPanel budget={obs.budget} />
      </section>

      <section aria-labelledby="events-title">
        <h3 id="events-title">运行事件</h3>
        <div className="stream-line">
          <p role="status" aria-live="polite" data-stream-state={obs.stream.state}>
            {STREAM_TEXT[obs.stream.state]}
            {obs.stream.state === 'reconnecting' && obs.stream.attempt > 0 ? `(第 ${obs.stream.attempt} 次)` : ''}
          </p>
          {obs.stream.state === 'closed' || obs.stream.state === 'polling' ? (
            <Button variant="quiet" onClick={obs.reconnect}>
              重新连接事件流
            </Button>
          ) : null}
          {obs.refreshError ? (
            <p className="notice notice--warn" role="status">
              刷新运行状态失败,显示的可能不是最新状态。
              <Button variant="quiet" onClick={obs.refreshNow}>
                重试
              </Button>
            </p>
          ) : null}
        </div>
        <EventLog events={obs.events} />
      </section>

      <section aria-labelledby="run-proposals-title">
        <h3 id="run-proposals-title">本次运行生成的提案</h3>
        <RunProposals run={run} refreshKey={proposalKey} />
      </section>

      {cancelOpen ? <CancelDialog run={run} onClose={() => setCancelOpen(false)} onDone={onRunChanged} /> : null}
    </div>
  );
}
