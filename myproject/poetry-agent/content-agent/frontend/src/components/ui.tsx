import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { clampPercent } from '../lib/format';

// ---------- Button ----------

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'quiet';
  /** 禁用并保持可聚焦:读屏用户仍能通过 aria-describedby 读到原因。 */
  blocked?: boolean;
}

/**
 * 用 aria-disabled 而不是 disabled 表达“被规则挡住”:按钮仍可聚焦,
 * 调用方用 aria-describedby 指向原因文字。点击被吞掉。
 */
export function Button({ variant = 'secondary', blocked = false, onClick, className, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      aria-disabled={blocked || rest.disabled ? true : undefined}
      className={['btn', `btn--${variant}`, className].filter(Boolean).join(' ')}
      onClick={event => {
        if (blocked) {
          event.preventDefault();
          return;
        }
        onClick?.(event);
      }}
    />
  );
}

// ---------- Chip(状态不只靠颜色:字形 + 文字) ----------

export type Tone = 'active' | 'review' | 'done' | 'bad' | 'idle';

export function Chip({ tone, glyph, label, code }: { tone: Tone; glyph: string; label: string; code?: string }) {
  return (
    <span className={`chip chip--${tone}`} title={code}>
      <span aria-hidden="true" className="chip__glyph">
        {glyph}
      </span>
      {label}
    </span>
  );
}

const RUN: Record<string, [Tone, string, string]> = {
  CREATED: ['idle', '○', '已创建'],
  RUNNING: ['active', '▶', '运行中'],
  WAITING_FOR_RUNTIME: ['review', '…', '等待运行时'],
  AWAITING_REVIEW: ['review', '◆', '待评审'],
  COMPLETED: ['done', '✓', '已完成'],
  FAILED: ['bad', '✕', '失败'],
};
export function RunStatusChip({ status }: { status: string }) {
  const [tone, glyph, label] = RUN[status] ?? ['idle', '?', status];
  return <Chip tone={tone} glyph={glyph} label={label} code={status} />;
}

const PROPOSAL: Record<string, [Tone, string, string]> = {
  REVIEW_REQUIRED: ['review', '◆', '待评审'],
  APPROVED: ['done', '✓', '已批准'],
  REJECTED: ['bad', '✕', '已驳回'],
  APPLIED: ['done', '↧', '已写入草稿'],
};
export function ProposalStatusChip({ status }: { status: string }) {
  const [tone, glyph, label] = PROPOSAL[status] ?? ['idle', '?', status];
  return <Chip tone={tone} glyph={glyph} label={label} code={status} />;
}

const VERIFY: Record<string, [Tone, string, string]> = {
  PENDING: ['review', '◇', '待核验'],
  VERIFIED: ['done', '✓', '已核验'],
  REJECTED: ['bad', '✕', '已驳回'],
};
export function VerificationChip({ status }: { status: string }) {
  const [tone, glyph, label] = VERIFY[status] ?? ['idle', '?', status];
  return <Chip tone={tone} glyph={glyph} label={label} code={status} />;
}

const LOCATOR: Record<string, [Tone, string, string]> = {
  SET: ['done', '✓', 'locator 已填'],
  MISSING: ['bad', '✕', 'locator 缺失'],
  PLACEHOLDER: ['review', '△', 'locator 是占位词'],
};
export function LocatorChip({ state }: { state: string }) {
  const [tone, glyph, label] = LOCATOR[state] ?? ['idle', '?', state];
  return <Chip tone={tone} glyph={glyph} label={label} code={state} />;
}

const RULE: Record<string, [Tone, string, string]> = {
  PASS: ['done', '✓', '通过'],
  FAIL: ['bad', '✕', '失败'],
  NOT_EVALUATED: ['idle', '–', '未评估'],
};
export function RuleStatusChip({ status }: { status: string }) {
  const [tone, glyph, label] = RULE[status] ?? ['idle', '?', status];
  return <Chip tone={tone} glyph={glyph} label={label} code={status} />;
}

/** PUBLISHED 与 DRAFT 永久区分:文字 + 字形 + 边框样式(实线/虚线),不靠颜色。 */
const CONTENT: Record<string, [string, string, string]> = {
  PUBLISHED: ['published', '■', '已发布 PUBLISHED'],
  DRAFT: ['draft', '□', '草稿 DRAFT'],
  IN_REVIEW: ['review', '◧', '审核中 IN_REVIEW'],
  RETRACTED: ['retracted', '⊘', '已撤回 RETRACTED'],
};
export function ContentStatusMark({ status }: { status: string | undefined }) {
  if (!status) return <span className="status-mark status-mark--none">状态未知</span>;
  const [kind, glyph, label] = CONTENT[status] ?? ['draft', '?', status];
  return (
    <span className={`status-mark status-mark--${kind}`} data-status={status}>
      <span aria-hidden="true">{glyph}</span> {label}
    </span>
  );
}

// ---------- Meter(数字 + 文字 + 条形) ----------

export function Meter({
  label,
  value,
  max,
  valueText,
  warnAt = 80,
}: {
  label: string;
  value: number | null;
  max: number | null;
  valueText: string;
  warnAt?: number;
}) {
  const pct = value !== null && max !== null && max > 0 ? Math.round((value / max) * 100) : null;
  const level = pct === null ? 'none' : pct >= 100 ? 'full' : pct >= warnAt ? 'near' : 'ok';
  const note = level === 'full' ? '已达上限' : level === 'near' ? '接近上限' : '';
  return (
    <div className={`meter meter--${level}`}>
      <div className="meter__head">
        <span className="meter__label">{label}</span>
        <span className="meter__value">
          {valueText}
          {pct !== null ? `(${pct}%)` : ''}
          {note ? ` · ${note}` : ''}
        </span>
      </div>
      <div
        className="meter__track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max ?? 0}
        aria-valuenow={value ?? 0}
        aria-valuetext={`${valueText}${pct !== null ? `,${pct}%` : ''}${note ? `,${note}` : ''}`}
      >
        <div className="meter__fill" style={{ width: `${clampPercent(pct)}%` }} />
      </div>
    </div>
  );
}

// ---------- Pager ----------

export function Pager({
  offset,
  limit,
  count,
  hasMore,
  onChange,
}: {
  offset: number;
  limit: number;
  count: number;
  hasMore: boolean;
  onChange: (offset: number) => void;
}) {
  const page = Math.floor(offset / Math.max(limit, 1)) + 1;
  const hasPrev = offset > 0;
  if (!hasPrev && !hasMore) return null;
  return (
    <nav className="pager" aria-label="分页">
      <Button variant="quiet" blocked={!hasPrev} onClick={() => onChange(Math.max(0, offset - limit))}>
        上一页
      </Button>
      <span aria-live="polite">
        第 {page} 页 · 本页 {count} 条
      </span>
      <Button variant="quiet" blocked={!hasMore} onClick={() => onChange(offset + limit)}>
        下一页
      </Button>
    </nav>
  );
}

// ---------- Field ----------

export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  children: (aria: { id: string; 'aria-describedby': string | undefined; 'aria-invalid': true | undefined }) => ReactNode;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;
  return (
    <div className={`field${error ? ' field--invalid' : ''}`}>
      <label htmlFor={id} className="field__label">
        {label}
      </label>
      {children({ id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })}
      {hint ? (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="field__error">
          <span aria-hidden="true">✕ </span>
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** 页面标题:路由切换后获得焦点并更新 document.title,读屏用户知道已换页。 */
export function PageHeader({ title, lead, actions }: { title: string; lead?: ReactNode; actions?: ReactNode }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = `${title} · Poetry Studio`;
    ref.current?.focus();
  }, [title]);
  return (
    <header className="page-header">
      <div>
        <h1 ref={ref} tabIndex={-1}>
          {title}
        </h1>
        {lead ? <p className="page-header__lead">{lead}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}
