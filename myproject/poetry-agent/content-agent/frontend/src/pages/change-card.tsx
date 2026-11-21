import type { DiffChange, ItemDecisionValue } from '../api/types';
import { isRecord } from '../lib/guards';
import type { LocalDecision } from '../lib/review-rules';

const LABEL_KIND: Record<string, string> = {
  来源请求: 'request',
  解释: 'interp',
  演绎: 'drama',
  草稿: 'draft',
  未考: 'unknown',
  缺口: 'gap',
};

export function labelKind(label: string): string {
  return LABEL_KIND[label] ?? 'draft';
}

function scalar(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

function KeyValues({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return <p className="muted">(空)</p>;
  return (
    <dl className="kv">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{scalar(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ChangeCard({
  change,
  decision,
  canDecide,
  recorded,
  onDecide,
}: {
  change: DiffChange;
  decision: LocalDecision | undefined;
  /** 是否允许现在做逐项决定(提案待评审且角色允许)。 */
  canDecide: boolean;
  /** 提案已评审时,显示服务端已记录的决定(只读)。 */
  recorded: boolean;
  onDecide: (index: number, next: Partial<LocalDecision>) => void;
}) {
  const kind = labelKind(change.label);
  const headingId = `change-${change.index}-title`;
  const name = `item-${change.index}`;
  const current = decision?.decision ?? null;

  return (
    <li className={`change change--${kind}`} aria-labelledby={headingId}>
      <header className="change__head">
        <span className="change__index">#{change.index}</span>
        <span className={`badge badge--${kind}`} id={headingId}>
          {change.label}
        </span>
        <code>{change.change_type}</code>
        <code className="muted">{change.classification}</code>
        {change.executable ? (
          <span className="exec exec--yes">可执行 · 批准后写入草稿</span>
        ) : (
          <span className="exec exec--no">仅留存 · 不会写入内容</span>
        )}
        {change.target_ref ? <span className="change__target">目标 {change.target_ref}</span> : null}
      </header>

      <div className="change__cols">
        <div>
          <h4>现状(before)</h4>
          {change.before ? <KeyValues data={change.before} /> : <p className="muted">无对应现有内容(新增)。</p>}
        </div>
        <div>
          <h4>提议(after)</h4>
          <div className={`after after--${kind}`}>{change.after}</div>
        </div>
      </div>

      {change.annotation && isRecord(change.annotation) ? (
        <details className="change__annotation">
          <summary>注释细节(写入草稿的字段)</summary>
          <KeyValues data={change.annotation} />
        </details>
      ) : null}

      <div className="change__risks">
        <h4>风险</h4>
        {change.risks.length > 0 ? (
          <ul>
            {change.risks.map(risk => (
              <li key={risk}>
                <span aria-hidden="true">△ </span>
                {risk}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">规则没有发现风险(不代表没有风险,仍需人工判断)。</p>
        )}
      </div>

      {change.executable ? (
        recorded ? (
          <p className="change__recorded">
            服务端记录的逐项决定:
            <strong>
              {change.item_decision ? (change.item_decision.decision === 'APPROVE' ? ' 批准' : ' 驳回') : ' 未记录'}
            </strong>
            {change.item_decision?.comment ? `(${change.item_decision.comment})` : ''}
          </p>
        ) : (
          <fieldset className="decision" disabled={!canDecide}>
            <legend>第 {change.index} 项的决定(必填)</legend>
            {(['APPROVE', 'REJECT'] as ItemDecisionValue[]).map(value => (
              <label key={value} className="radio">
                <input
                  type="radio"
                  name={name}
                  value={value}
                  checked={current === value}
                  onChange={() => onDecide(change.index, { decision: value })}
                />
                <span>{value === 'APPROVE' ? '批准此项(写入草稿)' : '驳回此项'}</span>
              </label>
            ))}
            <label className="decision__comment">
              <span>评语(可选)</span>
              <input
                value={decision?.comment ?? ''}
                onChange={event => onDecide(change.index, { comment: event.target.value })}
                aria-label={`第 ${change.index} 项评语`}
              />
            </label>
          </fieldset>
        )
      ) : (
        <p className="change__recorded muted">此项不是可执行项,不需要逐项决定。</p>
      )}
    </li>
  );
}
