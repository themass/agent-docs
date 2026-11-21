import { useState } from 'react';
import { applyProposal, getProposal, getProposalDiff, reviewProposal } from '../api/client';
import type { DiffChange, ItemDecisionValue, Proposal, ProposalDiff } from '../api/types';
import { useAnnounce } from '../components/announcer';
import { AsyncView } from '../components/async-view';
import { Dialog } from '../components/dialog';
import { ErrorDetails } from '../components/error-details';
import { Button, Field, PageHeader, ProposalStatusChip } from '../components/ui';
import { useActor } from '../lib/actor';
import { describeError, detailOf, errorCode } from '../lib/errors';
import { formatTime } from '../lib/format';
import { applyDenyReason, canReview } from '../lib/permissions';
import {
  buildItemDecisions,
  countApprovedExecutable,
  executableIndexes,
  initialDecisions,
  reviewGate,
  undecidedIndexes,
  type Decisions,
  type LocalDecision,
} from '../lib/review-rules';
import { useAsync } from '../lib/use-async';
import { ChangeCard } from './change-card';

interface Flash {
  tone: 'ok' | 'info';
  text: string;
}

// ---------- 整体评审对话框 ----------

function ReviewDialog({
  proposal,
  changes,
  decisions,
  action,
  onClose,
  onDone,
}: {
  proposal: Proposal;
  changes: DiffChange[];
  decisions: Decisions;
  action: ItemDecisionValue;
  onClose: () => void;
  onDone: (flash: Flash) => void;
}) {
  const { actor, bodyActor, mode } = useActor();
  const announce = useAnnounce();
  const [comment, setComment] = useState('');
  const [commentError, setCommentError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const executable = executableIndexes(changes);
  const approved = countApprovedExecutable(changes, decisions);
  const rejected = executable.length - approved;
  const approving = action === 'APPROVE';

  const submit = async () => {
    if (pending) return;
    if (!approving && comment.trim() === '') {
      setCommentError('驳回必须写评语,说明原因。');
      return;
    }
    setCommentError(null);
    setError(null);
    setPending(true);
    try {
      const itemDecisions = buildItemDecisions(changes, decisions);
      await reviewProposal(proposal.proposal_id, {
        ...(bodyActor ? { actor: bodyActor } : {}),
        decision: action,
        ...(comment.trim() ? { comment: comment.trim() } : {}),
        ...(itemDecisions.length > 0 ? { item_decisions: itemDecisions } : {}),
      });
      const text = approving ? '提案已批准。批准只允许写入草稿,尚未写入,也没有发布。' : '提案已驳回。';
      announce(text);
      onDone({ tone: 'ok', text });
    } catch (e) {
      setError(e);
      announce(`评审失败:${describeError(e).message}`, true);
    } finally {
      setPending(false);
    }
  };

  const missing = detailOf(error, 'missing_item_index');
  const code = errorCode(error);

  return (
    <Dialog
      title={approving ? '整体批准这个提案?' : '整体驳回这个提案?'}
      onClose={onClose}
      busy={pending}
      footer={
        <>
          <Button variant="quiet" onClick={onClose} blocked={pending}>
            返回
          </Button>
          <Button variant="primary" onClick={() => void submit()} blocked={pending}>
            {pending ? '正在提交…' : approving ? '确认批准' : '确认驳回'}
          </Button>
        </>
      }
    >
      {approving ? (
        <>
          <p>
            批准的含义:被逐项批准的可执行项<strong>可以</strong>在下一步“写入草稿”。批准<strong>不会发布</strong>任何内容,也不会核验来源。
          </p>
          <p className="num">
            可执行项 {executable.length} 个:批准 {approved} 个,驳回 {rejected} 个。
          </p>
          {executable.length === 0 || approved === 0 ? (
            <p className="notice notice--info">
              没有可写入草稿的项。批准后该提案只作为编辑记录留存,运行直接完成。
            </p>
          ) : null}
        </>
      ) : (
        <p>驳回后该提案不能再应用。已做的逐项决定会一并记录。</p>
      )}
      <Field
        id="review-comment"
        label={approving ? '评语(可选)' : '评语(必填)'}
        error={commentError}
        hint="评语会写入审计记录。"
      >
        {aria => (
          <textarea
            {...aria}
            data-autofocus
            rows={3}
            value={comment}
            onChange={event => {
              setComment(event.target.value);
              setCommentError(null);
            }}
          />
        )}
      </Field>
      <p className="field__hint">
        {mode === 'off' ? '将以占位身份 ' : '将以登录身份 '}
        <code>{actor.actor_id}</code>({actor.role})提交。
      </p>
      {error ? (
        <div className="notice notice--error" role="alert">
          <p>
            <span aria-hidden="true">✕ </span>
            {describeError(error).message}
            {code ? (
              <>
                {' '}
                <code>{code}</code>
              </>
            ) : null}
          </p>
          {code === 'ITEM_DECISIONS_REQUIRED' && Array.isArray(missing) ? (
            <p>服务端指出这些可执行项还没有决定:第 {missing.join('、')} 项。请关闭对话框后补全。</p>
          ) : (
            <ErrorDetails details={describeError(error).details} />
          )}
          {code === 'PROPOSAL_NOT_REVIEWABLE' ? <p>该提案已不是待评审状态,请刷新页面查看最新状态。</p> : null}
        </div>
      ) : null}
    </Dialog>
  );
}

// ---------- 应用(写入草稿)对话框 ----------

function ApplyDialog({
  proposal,
  onClose,
  onDone,
}: {
  proposal: Proposal;
  onClose: () => void;
  onDone: (flash: Flash) => void;
}) {
  const { actor, bodyActor, mode } = useActor();
  const announce = useAnnounce();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const confirm = async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await applyProposal(proposal.proposal_id, bodyActor);
      const text = '已写入草稿。内容仍是 DRAFT,尚未发布。';
      announce(text);
      onDone({ tone: 'ok', text });
    } catch (e) {
      if (errorCode(e) === 'NOTHING_TO_APPLY') {
        const text = '没有被批准的可执行项,无内容可写入。该提案只作为编辑记录留存。';
        announce(text);
        onDone({ tone: 'info', text });
        return;
      }
      setError(e);
      announce(`写入草稿失败:${describeError(e).message}`, true);
    } finally {
      setPending(false);
    }
  };

  const code = errorCode(error);
  return (
    <Dialog
      title="把已批准的项写入草稿?"
      onClose={onClose}
      busy={pending}
      footer={
        <>
          <Button variant="quiet" onClick={onClose} blocked={pending}>
            返回
          </Button>
          <Button variant="primary" onClick={() => void confirm()} blocked={pending} data-autofocus>
            {pending ? '正在写入…' : '写入草稿(不是发布)'}
          </Button>
        </>
      }
    >
      <p>
        这一步只把<strong>被逐项批准的可执行项</strong>写入内容库的 <code>DRAFT</code> 区。它<strong>不是发布</strong>:不会让学生看到,也不会核验来源。
      </p>
      <p className="field__hint">
        {mode === 'off' ? '将以占位身份 ' : '将以登录身份 '}
        <code>{actor.actor_id}</code>({actor.role})提交。
      </p>
      {error ? (
        <div className="notice notice--error" role="alert">
          <p>
            <span aria-hidden="true">✕ </span>
            {describeError(error).message}
            {code ? (
              <>
                {' '}
                <code>{code}</code>
              </>
            ) : null}
          </p>
          {code === 'ITEMS_UNAVAILABLE' ? <p>逐项决定暂时读不到,可以稍后重试。</p> : null}
          {code === 'PROPOSAL_NOT_APPLICABLE' ? <p>提案状态已变化,请刷新页面。</p> : null}
          <ErrorDetails details={describeError(error).details} />
        </div>
      ) : null}
    </Dialog>
  );
}

// ---------- 审核工作区 ----------

function ReviewWorkspace({
  proposal,
  diff,
  onChanged,
}: {
  proposal: Proposal;
  diff: ProposalDiff;
  onChanged: (flash: Flash) => void;
}) {
  const { actor } = useActor();
  const [decisions, setDecisions] = useState<Decisions>(() => initialDecisions(diff.changes));
  const [dialog, setDialog] = useState<'APPROVE' | 'REJECT' | 'APPLY' | null>(null);

  const changes = diff.changes;
  const executable = executableIndexes(changes);
  const pendingReview = proposal.status === 'REVIEW_REQUIRED';
  const common = { status: proposal.status, role: actor.role, actorId: actor.actor_id, changes, decisions };
  const approveGate = reviewGate({ ...common, action: 'APPROVE' });
  const rejectGate = reviewGate({ ...common, action: 'REJECT' });
  const canDecide = rejectGate.allowed;
  const reasons = [...new Set([approveGate.reason, rejectGate.reason].filter((r): r is string => r !== null))];
  const decidedCount = executable.length - undecidedIndexes(changes, decisions).length;

  const onDecide = (index: number, next: Partial<LocalDecision>) =>
    setDecisions(current => ({
      ...current,
      [index]: { decision: current[index]?.decision ?? null, comment: current[index]?.comment ?? '', ...next },
    }));

  const approvedCount = proposal.approved_executable_count;
  const applyReason = applyDenyReason(actor.role);
  const nothingToApply = approvedCount === 0;

  return (
    <>
      <section aria-labelledby="changes-title">
        <h2 id="changes-title">逐项改动</h2>
        <ol className="changes">
          {changes.map(change => (
            <ChangeCard
              key={change.index}
              change={change}
              decision={decisions[change.index]}
              canDecide={canDecide}
              recorded={!pendingReview}
              onDecide={onDecide}
            />
          ))}
        </ol>
      </section>

      {pendingReview ? (
        <section aria-labelledby="overall-title" className="panel panel--sticky">
          <h2 id="overall-title">整体评审</h2>
          <p role="status" aria-live="polite" className="num">
            可执行项 {executable.length} 个,已逐项决定 {decidedCount} 个。
          </p>
          {reasons.length > 0 ? (
            <ul id="review-reasons" className="reasons">
              {reasons.map(reason => (
                <li key={reason}>
                  <span aria-hidden="true">△ </span>
                  {reason}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">所有可执行项都已决定,可以整体批准;也可以直接驳回。</p>
          )}
          <div className="actions">
            <Button
              variant="primary"
              blocked={!approveGate.allowed}
              aria-describedby={!approveGate.allowed ? 'review-reasons' : undefined}
              onClick={() => setDialog('APPROVE')}
            >
              整体批准 APPROVE
            </Button>
            <Button
              variant="secondary"
              blocked={!rejectGate.allowed}
              aria-describedby={!rejectGate.allowed ? 'review-reasons' : undefined}
              onClick={() => setDialog('REJECT')}
            >
              整体驳回 REJECT
            </Button>
          </div>
          <p className="field__hint">批准只表示允许下一步写入草稿,不是发布。</p>
        </section>
      ) : (
        <section aria-labelledby="applied-title" className="panel">
          <h2 id="applied-title">写入草稿</h2>
          {proposal.status === 'APPLIED' ? (
            <p>
              <span aria-hidden="true">↧ </span>
              已于 <span className="num">{formatTime(proposal.applied_at)}</span> 写入草稿。内容仍是 DRAFT,<strong>尚未发布</strong>。
            </p>
          ) : null}
          {proposal.status === 'REJECTED' ? <p>提案已驳回,不会写入任何内容。</p> : null}
          {proposal.status === 'APPROVED' ? (
            <>
              {nothingToApply ? (
                <p className="notice notice--info">
                  没有被批准的可执行项(NOTHING_TO_APPLY)。该提案只作为编辑记录留存,无内容可写入。
                </p>
              ) : (
                <>
                  <p>
                    已批准 {approvedCount ?? '若干'} 个可执行项。下一步把它们写入<strong>草稿</strong>,这<strong>不是发布</strong>。
                  </p>
                  {applyReason ? (
                    <p id="apply-reason" className="reasons">
                      <span aria-hidden="true">△ </span>
                      {applyReason}
                    </p>
                  ) : null}
                  <Button
                    variant="primary"
                    blocked={applyReason !== null}
                    aria-describedby={applyReason ? 'apply-reason' : undefined}
                    onClick={() => setDialog('APPLY')}
                  >
                    写入草稿(不是发布)
                  </Button>
                </>
              )}
            </>
          ) : null}
        </section>
      )}

      {dialog === 'APPROVE' || dialog === 'REJECT' ? (
        <ReviewDialog
          proposal={proposal}
          changes={changes}
          decisions={decisions}
          action={dialog}
          onClose={() => setDialog(null)}
          onDone={flash => {
            setDialog(null);
            onChanged(flash);
          }}
        />
      ) : null}
      {dialog === 'APPLY' ? (
        <ApplyDialog
          proposal={proposal}
          onClose={() => setDialog(null)}
          onDone={flash => {
            setDialog(null);
            onChanged(flash);
          }}
        />
      ) : null}
    </>
  );
}

// ---------- 页面 ----------

function ActorBanner() {
  const { actor, mode } = useActor();
  const allowed = canReview(actor.role);
  return (
    <p className={`notice ${allowed ? 'notice--info' : 'notice--warn'}`}>
      {mode === 'off' ? '当前占位身份' : '当前登录身份'}:<code>{actor.actor_id}</code>({actor.role})。
      {allowed
        ? ' 可以评审。服务端仍会再次校验。'
        : mode === 'off'
          ? ' 该角色不能评审提案(只有 CONTENT_EDITOR / HISTORICAL_REVIEWER 可以),逐项与整体操作已禁用。可在右上角切换身份。'
          : ' 该角色不能评审提案(只有 CONTENT_EDITOR / HISTORICAL_REVIEWER 可以),逐项与整体操作已禁用。请联系管理员调整账号角色。'}
    </p>
  );
}

export function ProposalDetailPage({ proposalId }: { proposalId: string }) {
  const [flash, setFlash] = useState<Flash | null>(null);
  const result = useAsync(
    async signal => {
      const [proposal, diff] = await Promise.all([getProposal(proposalId, signal), getProposalDiff(proposalId, signal)]);
      return { proposal, diff };
    },
    [proposalId],
  );

  return (
    <>
      <PageHeader
        title="提案审核"
        lead={
          <>
            <a href="#/proposals">← 返回提案列表</a>
          </>
        }
      />
      {flash ? (
        <p className={`notice ${flash.tone === 'ok' ? 'notice--ok' : 'notice--info'}`} role="status">
          {flash.text}
        </p>
      ) : null}
      <AsyncView result={result} loadingLabel="正在加载提案与 diff…" errorTitle="提案加载失败">
        {({ proposal, diff }) => (
          <>
            <section aria-labelledby="proposal-title" className="panel">
              <h2 id="proposal-title">
                <code>{proposal.proposal_id}</code> <ProposalStatusChip status={proposal.status} />
              </h2>
              <dl className="meta-grid">
                <div>
                  <dt>作品</dt>
                  <dd>
                    <code>{proposal.work_id}</code>
                  </dd>
                </div>
                <div>
                  <dt>来源运行</dt>
                  <dd>
                    <a href={`#/tasks/${encodeURIComponent(proposal.task_id ?? '')}?run=${encodeURIComponent(proposal.run_id)}`}>
                      <code>{proposal.run_id}</code>
                    </a>
                  </dd>
                </div>
                <div>
                  <dt>创建</dt>
                  <dd className="num">{formatTime(proposal.created_at)}</dd>
                </div>
                <div>
                  <dt>评审</dt>
                  <dd>{proposal.reviewed_by ? `${proposal.reviewed_by}${proposal.review_comment ? `:${proposal.review_comment}` : ''}` : '尚未评审'}</dd>
                </div>
                <div>
                  <dt>快照时间</dt>
                  <dd className="num">{formatTime(diff.snapshot_taken_at)}</dd>
                </div>
              </dl>
              {proposal.payload?.summary ? <p className="prose-summary">{proposal.payload.summary}</p> : null}
              {proposal.payload?.human_review_question ? (
                <p className="question">
                  <strong>需要你回答:</strong>
                  {proposal.payload.human_review_question}
                </p>
              ) : null}
              {proposal.payload?.unknowns && proposal.payload.unknowns.length > 0 ? (
                <details>
                  <summary>agent 标出的未知项({proposal.payload.unknowns.length})</summary>
                  <ul>
                    {proposal.payload.unknowns.map(item => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </section>

            <ActorBanner />

            <ReviewWorkspace
              key={`${proposal.status}:${proposal.applied_at ?? ''}`}
              proposal={proposal}
              diff={diff}
              onChanged={next => {
                setFlash(next);
                result.refresh();
              }}
            />
          </>
        )}
      </AsyncView>
    </>
  );
}
