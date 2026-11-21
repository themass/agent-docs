import { useState } from 'react';
import { getReadiness, listSources, postVerification, putLocator, sourceIdOf } from '../api/client';
import type { Source, SourceCitation } from '../api/types';
import { useAnnounce } from '../components/announcer';
import { AsyncView, EmptyView, ErrorView } from '../components/async-view';
import { Dialog } from '../components/dialog';
import { Button, Field, LocatorChip, PageHeader, Pager, VerificationChip } from '../components/ui';
import { useActor } from '../lib/actor';
import { describeError, errorCode } from '../lib/errors';
import { sourceDenyReason } from '../lib/permissions';
import { navigate, useQueryUpdater, useRoute } from '../lib/router';
import { useAsync } from '../lib/use-async';
import { validateLocator, validateSignature } from '../lib/validation';

const PAGE_SIZE = 20;

/** off 模式:署名作为 actor_id 随请求体提交;required 模式:不带 actor,服务端以令牌为准。 */
function actorField(mode: 'off' | 'required', signature: string, role: Parameters<typeof sourceDenyReason>[0]) {
  return mode === 'off' ? { actor: { actor_id: signature.trim(), role } } : {};
}

export interface VerifyGate {
  allowed: boolean;
  reasons: string[];
}

/** VERIFY 的前端门槛:角色、署名、且所有 citation 的 locator_state 必须为 SET。后端为准。 */
export function verifyGate(role: Parameters<typeof sourceDenyReason>[0], signature: string, citations: SourceCitation[]): VerifyGate {
  const reasons: string[] = [];
  const roleReason = sourceDenyReason(role);
  if (roleReason) reasons.push(roleReason);
  const sig = validateSignature(signature);
  if (sig) reasons.push(`署名:${sig}`);
  for (const c of citations) {
    if (c.locator_state !== 'SET') {
      reasons.push(`claim ${c.claim_id} 的 locator 状态是 ${c.locator_state},必须先填写真实 locator 并保存。`);
    }
  }
  return { allowed: reasons.length === 0, reasons };
}

export function rejectGate(role: Parameters<typeof sourceDenyReason>[0], signature: string): VerifyGate {
  const reasons: string[] = [];
  const roleReason = sourceDenyReason(role);
  if (roleReason) reasons.push(roleReason);
  const sig = validateSignature(signature);
  if (sig) reasons.push(`署名:${sig}`);
  return { allowed: reasons.length === 0, reasons };
}

function CitationEditor({
  source,
  citation,
  signature,
  disabled,
  onSaved,
}: {
  source: Source;
  citation: SourceCitation;
  signature: string;
  disabled: boolean;
  onSaved: () => void;
}) {
  const { actor, mode } = useActor();
  const announce = useAnnounce();
  const [locator, setLocator] = useState(citation.locator_state === 'SET' ? citation.locator ?? '' : '');
  const [excerpt, setExcerpt] = useState(citation.evidence_excerpt ?? '');
  const [note, setNote] = useState('');
  const [locatorError, setLocatorError] = useState<string | null>(null);
  const [sigError, setSigError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const id = `cit-${citation.claim_id}`;

  const save = async () => {
    if (pending) return;
    const lerr = validateLocator(locator);
    const serr = validateSignature(signature);
    setLocatorError(lerr);
    setSigError(serr);
    setError(null);
    setSaved(false);
    if (lerr || serr) {
      announce('表单有错误,请修正后再保存。', true);
      return;
    }
    setPending(true);
    try {
      await putLocator(citation.claim_id, sourceIdOf(source), {
        ...actorField(mode, signature, actor.role),
        locator: locator.trim(),
        ...(excerpt.trim() ? { evidence_excerpt: excerpt.trim() } : {}),
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      setSaved(true);
      announce('locator 已保存。');
      onSaved();
    } catch (e) {
      setError(e);
      announce(`保存失败:${describeError(e).message}`, true);
    } finally {
      setPending(false);
    }
  };

  return (
    <li className="citation">
      <header className="citation__head">
        <strong>
          claim <code>{citation.claim_id}</code>
        </strong>
        <LocatorChip state={citation.locator_state} />
      </header>
      <p className="citation__claim">
        {citation.claim_value ?? '(无 claim 文本)'}
        {citation.claim_kind ? <span className="muted"> · {citation.claim_kind}</span> : null}
        {citation.claim_status ? <span className="muted"> · {citation.claim_status}</span> : null}
      </p>
      <fieldset className="citation__form" disabled={disabled}>
        <legend className="sr-only">填写 claim {citation.claim_id} 的出处定位</legend>
        <Field
          id={`${id}-locator`}
          label="locator(卷/页/篇名)"
          hint="只填你亲自对照原文核对过的定位。不要照抄 agent 的猜测,也不要填占位词。"
          error={locatorError}
        >
          {aria => <input {...aria} value={locator} onChange={e => setLocator(e.target.value)} />}
        </Field>
        <Field id={`${id}-excerpt`} label="摘录(可选)" hint="原文摘录,便于复核。">
          {aria => <textarea {...aria} rows={2} value={excerpt} onChange={e => setExcerpt(e.target.value)} />}
        </Field>
        <Field id={`${id}-note`} label="备注(可选)">
          {aria => <input {...aria} value={note} onChange={e => setNote(e.target.value)} />}
        </Field>
        {sigError ? (
          <p className="field__error" role="alert">
            <span aria-hidden="true">✕ </span>
            {sigError}
          </p>
        ) : null}
        <Button variant="secondary" blocked={pending} onClick={() => void save()}>
          {pending ? '正在保存…' : '保存 locator'}
        </Button>
        {saved ? (
          <span className="saved" role="status">
            ✓ 已保存
          </span>
        ) : null}
      </fieldset>
      {error ? <ErrorView error={error} title="locator 保存失败" /> : null}
    </li>
  );
}

function DecisionDialog({
  source,
  decision,
  signature,
  onClose,
  onDone,
}: {
  source: Source;
  decision: 'VERIFY' | 'REJECT';
  signature: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const { actor, mode } = useActor();
  const announce = useAnnounce();
  const [note, setNote] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const verifying = decision === 'VERIFY';

  const submit = async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await postVerification(sourceIdOf(source), {
        ...actorField(mode, signature, actor.role),
        decision,
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      announce(verifying ? '来源已核验。' : '来源已驳回。');
      onDone();
    } catch (e) {
      setError(e);
      announce(`操作失败:${describeError(e).message}`, true);
    } finally {
      setPending(false);
    }
  };

  const code = errorCode(error);
  return (
    <Dialog
      title={verifying ? '核验这个来源?' : '驳回这个来源?'}
      onClose={onClose}
      busy={pending}
      footer={
        <>
          <Button variant="quiet" onClick={onClose} blocked={pending}>
            返回
          </Button>
          <Button variant="primary" onClick={() => void submit()} blocked={pending}>
            {pending ? '正在提交…' : verifying ? '确认核验' : '确认驳回'}
          </Button>
        </>
      }
    >
      <p>
        来源 <strong>{source.title ?? sourceIdOf(source)}</strong>(<code>{sourceIdOf(source)}</code>)
      </p>
      {verifying ? (
        <p>
          这是人工的史料判断。服务端会走发布闸门并运行全量审计;署名 <strong>{signature.trim()}</strong> 会写入审计记录。agent 没有这个权限。
        </p>
      ) : (
        <p>驳回后该来源不能支撑任何 claim。署名 <strong>{signature.trim()}</strong> 会写入审计记录。</p>
      )}
      <Field id="decision-note" label="备注(可选)">
        {aria => <textarea {...aria} data-autofocus rows={3} value={note} onChange={e => setNote(e.target.value)} />}
      </Field>
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
          {code === 'STUDIO_CONFLICT' ? <p>服务端认为状态冲突,常见原因是仍有 citation 缺少 locator。详情:</p> : null}
          {code === 'STUDIO_UNAVAILABLE' ? <p>读写通道未配置(reviewer 令牌或 Java 地址)。这是部署问题,不是你的操作错误。</p> : null}
          <ErrorDetailsInline error={error} />
        </div>
      ) : null}
    </Dialog>
  );
}

function ErrorDetailsInline({ error }: { error: unknown }) {
  const info = describeError(error);
  if (info.details === undefined || info.details === null) return null;
  return <pre className="details-pre">{typeof info.details === 'string' ? info.details : JSON.stringify(info.details, null, 2)}</pre>;
}

function SourceDetail({ source, onChanged }: { source: Source; onChanged: () => void }) {
  const { actor, mode } = useActor();
  const [signature, setSignature] = useState(actor.actor_id);
  const [dialog, setDialog] = useState<'VERIFY' | 'REJECT' | null>(null);
  const roleReason = sourceDenyReason(actor.role);
  const verify = verifyGate(actor.role, signature, source.citations);
  const reject = rejectGate(actor.role, signature);
  const sigError = signature.trim() === '' ? null : validateSignature(signature);

  return (
    <section aria-labelledby="source-detail-title" className="panel">
      <h2 id="source-detail-title">{source.title ?? sourceIdOf(source)}</h2>
      <dl className="meta-grid">
        <div>
          <dt>来源 id</dt>
          <dd>
            <code>{sourceIdOf(source)}</code>
          </dd>
        </div>
        <div>
          <dt>核验状态</dt>
          <dd>
            <VerificationChip status={source.verification_status} />
          </dd>
        </div>
        <div>
          <dt>类型 / 可靠度</dt>
          <dd>
            {source.source_kind ?? '—'} / {source.reliability ?? '—'}
          </dd>
        </div>
        <div>
          <dt>作者 / 版本</dt>
          <dd>
            {source.author ?? '—'} / {source.edition ?? '—'}
          </dd>
        </div>
      </dl>
      {source.url ? <p className="muted">链接:{source.url}</p> : null}

      {roleReason ? (
        <p className="notice notice--warn" id="source-role-reason">
          {roleReason} 下面的输入已禁用。
        </p>
      ) : null}

      <Field
        id="signature"
        label="署名(审核人姓名)"
        hint={
          mode === 'required'
            ? '署名取自你的登录身份,不能修改;服务端以令牌为准写入审计记录。'
            : '会作为审计署名随请求提交。必填,不能像 agent 或系统账号。'
        }
        error={sigError}
      >
        {aria => (
          <input
            {...aria}
            value={signature}
            readOnly={mode === 'required'}
            onChange={e => setSignature(e.target.value)}
            autoComplete="off"
          />
        )}
      </Field>

      <h3>支撑的 claim 与 locator</h3>
      {source.citations.length === 0 ? (
        <EmptyView title="这个来源没有被任何 claim 引用">没有 citation 需要填写。核验与否由服务端规则决定。</EmptyView>
      ) : (
        <ul className="citations">
          {source.citations.map(citation => (
            <CitationEditor
              key={citation.claim_id}
              source={source}
              citation={citation}
              signature={signature}
              disabled={roleReason !== null}
              onSaved={onChanged}
            />
          ))}
        </ul>
      )}

      <div className="actions">
        <Button
          variant="primary"
          blocked={!verify.allowed}
          aria-describedby={!verify.allowed ? 'verify-reasons' : undefined}
          onClick={() => setDialog('VERIFY')}
        >
          核验 VERIFY
        </Button>
        <Button
          variant="secondary"
          blocked={!reject.allowed}
          aria-describedby={!reject.allowed ? 'verify-reasons' : undefined}
          onClick={() => setDialog('REJECT')}
        >
          驳回 REJECT
        </Button>
      </div>
      {!verify.allowed ? (
        <ul id="verify-reasons" className="reasons">
          {verify.reasons.map(reason => (
            <li key={reason}>
              <span aria-hidden="true">△ </span>
              {reason}
            </li>
          ))}
        </ul>
      ) : null}

      {dialog ? (
        <DecisionDialog
          source={source}
          decision={dialog}
          signature={signature}
          onClose={() => setDialog(null)}
          onDone={() => {
            setDialog(null);
            onChanged();
          }}
        />
      ) : null}
    </section>
  );
}

function ChannelNotice() {
  const result = useAsync(signal => getReadiness(signal), []);
  if (result.state.status !== 'ready') return null;
  if (result.state.data.reviewer_token_configured !== false) return null;
  return (
    <p className="notice notice--error" role="status">
      BFF 报告 reviewer 通道未配置(reviewer_token_configured=false)。本页的写入会返回 503 STUDIO_UNAVAILABLE,这是部署问题。
    </p>
  );
}

export function SourcesPage() {
  const { query } = useRoute();
  const update = useQueryUpdater();
  const status = query.status ?? 'PENDING';
  const offset = Number(query.offset ?? '0') || 0;
  const selectedId = query.source ?? '';
  const result = useAsync(
    signal => listSources({ verification_status: status || undefined, limit: PAGE_SIZE, offset }, signal),
    [status, offset],
  );

  return (
    <>
      <PageHeader title="出处核查" lead="人工填写 locator、核验或驳回来源。这是史料判断,只能由人完成。" />
      <p className="notice notice--lock" role="note">
        <strong>agent 没有此权限。</strong>
        agent 不能填写 locator、核验或驳回来源。这里的每次写入都用你的署名记录审计。
      </p>
      <ChannelNotice />
      <form className="filters" role="search" aria-label="筛选来源" onSubmit={event => event.preventDefault()}>
        <div className="filters__item">
          <label htmlFor="sf-status">核验状态</label>
          <select id="sf-status" value={status} onChange={e => update({ status: e.target.value, offset: undefined, source: undefined })}>
            <option value="PENDING">待核验 PENDING</option>
            <option value="VERIFIED">已核验 VERIFIED</option>
            <option value="REJECTED">已驳回 REJECTED</option>
            <option value="">全部</option>
          </select>
        </div>
      </form>

      <AsyncView
        result={result}
        loadingLabel="正在加载来源…"
        errorTitle="来源列表加载失败"
        empty={page =>
          page.items.length === 0 ? (
            <EmptyView title={status === 'PENDING' ? '没有待核验的来源' : '没有符合条件的来源'}>
              {status === 'PENDING' ? '所有来源都已处理。可以切换筛选查看已核验或已驳回的来源。' : '换一个筛选条件试试。'}
            </EmptyView>
          ) : null
        }
      >
        {page => {
          const selected = page.items.find(s => sourceIdOf(s) === selectedId);
          return (
            <div className="split split--sources">
              <section aria-labelledby="source-list-title">
                <h2 id="source-list-title">来源列表</h2>
                <ul className="source-list">
                  {page.items.map(source => {
                    const id = sourceIdOf(source);
                    const missing = source.citations.filter(c => c.locator_state !== 'SET').length;
                    return (
                      <li key={id}>
                        <a
                          href={`#/sources?${new URLSearchParams({ ...(status !== 'PENDING' ? { status } : {}), source: id }).toString()}`}
                          aria-current={id === selectedId ? 'true' : undefined}
                        >
                          <span className="source-list__title">{source.title ?? id}</span>
                          <span className="source-list__meta">
                            <VerificationChip status={source.verification_status} />
                            <span>
                              支撑 {source.citations.length} 条 claim · {missing} 条 locator 未就绪
                            </span>
                          </span>
                        </a>
                      </li>
                    );
                  })}
                </ul>
                <Pager
                  offset={page.offset}
                  limit={page.limit || PAGE_SIZE}
                  count={page.items.length}
                  hasMore={page.has_more}
                  onChange={next => update({ offset: next === 0 ? undefined : String(next) })}
                />
              </section>
              <div>
                {selected ? (
                  <SourceDetail
                    key={`${sourceIdOf(selected)}:${selected.verification_status}`}
                    source={selected}
                    onChanged={result.refresh}
                  />
                ) : (
                  <EmptyView title="选择左侧的一个来源">
                    {selectedId ? `没有找到来源 ${selectedId}(可能已处理或不在当前筛选里)。` : '选中后在这里填写 locator 并核验。'}
                    {selectedId ? (
                      <Button variant="quiet" onClick={() => navigate('/sources', { status: status === 'PENDING' ? undefined : status }, true)}>
                        取消选择
                      </Button>
                    ) : null}
                  </EmptyView>
                )}
              </div>
            </div>
          );
        }}
      </AsyncView>
    </>
  );
}
