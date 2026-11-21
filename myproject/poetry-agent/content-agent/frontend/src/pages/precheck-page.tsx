import { useState } from 'react';
import { getPrecheck } from '../api/client';
import type { Precheck, PrecheckRule } from '../api/types';
import { AsyncView, EmptyView } from '../components/async-view';
import { Button, PageHeader, RuleStatusChip } from '../components/ui';
import { WorkScope } from '../components/work-scope';
import { formatTime } from '../lib/format';
import { RULE_GLOSS } from '../lib/labels';
import { useAsync } from '../lib/use-async';

const VERDICT: Record<string, { glyph: string; label: string }> = {
  READY_FOR_HUMAN_PUBLISH: { glyph: '◆', label: 'READY_FOR_HUMAN_PUBLISH · 具备交由人工决定是否发布的前置条件' },
  BLOCKED: { glyph: '✕', label: 'BLOCKED · 有规则失败,不能进入人工发布' },
  INCOMPLETE: { glyph: '–', label: 'INCOMPLETE · 有规则未评估,结论不完整' },
};

function RuleRow({ rule }: { rule: PrecheckRule }) {
  const [open, setOpen] = useState(false);
  const detailsId = `rule-${rule.id}-details`;
  return (
    <>
      <tr>
        <th scope="row">
          <code>{rule.id}</code>
        </th>
        <td>
          {rule.name}
          {RULE_GLOSS[rule.id] ? <span className="muted block">{RULE_GLOSS[rule.id]}</span> : null}
        </td>
        <td>
          <span className={`eval eval--${rule.evaluation.toLowerCase()}`}>{rule.evaluation}</span>
        </td>
        <td>
          <RuleStatusChip status={rule.status} />
        </td>
        <td>
          {rule.details.length > 0 ? (
            <Button variant="quiet" aria-expanded={open} aria-controls={detailsId} onClick={() => setOpen(v => !v)}>
              {open ? '收起详情' : `展开详情(${rule.details.length})`}
            </Button>
          ) : (
            <span className="muted">无详情</span>
          )}
        </td>
      </tr>
      {open ? (
        <tr id={detailsId} className="rule-details">
          <td colSpan={5}>
            <ul>
              {rule.details.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function PrecheckBody({ data }: { data: Precheck }) {
  const verdict = VERDICT[data.verdict] ?? { glyph: '?', label: data.verdict };
  const counts = { PASS: 0, FAIL: 0, NOT_EVALUATED: 0 } as Record<string, number>;
  for (const rule of data.rules) counts[rule.status] = (counts[rule.status] ?? 0) + 1;
  return (
    <>
      <section aria-labelledby="verdict-title" className={`verdict verdict--${data.verdict.toLowerCase()}`}>
        <h2 id="verdict-title">总判定</h2>
        <p className="verdict__label">
          <span aria-hidden="true">{verdict.glyph} </span>
          {verdict.label}
        </p>
        <p className="num">
          通过 {counts.PASS} · 失败 {counts.FAIL} · 未评估 {counts.NOT_EVALUATED} · 评估时间 {formatTime(data.evaluated_at)}
        </p>
        <p className="notice notice--lock" role="note">
          <strong>READY_FOR_HUMAN_PUBLISH 不等于已发布。</strong>
          这只表示前置条件满足,是否发布由人通过 Java 发布闸门决定。Poetry Studio 里没有、也不会有发布入口。
        </p>
        {data.note ? <p className="muted">{data.note}</p> : null}
      </section>

      <section aria-labelledby="bundle-title">
        <h2 id="bundle-title">bundle 状态</h2>
        {data.bundle.state === 'EVALUATED' ? (
          <p>
            已评估 bundle <code>{data.bundle.script_id ?? '—'}</code> 版本 <code>{data.bundle.script_version ?? '—'}</code>。
          </p>
        ) : (
          <p className="notice notice--info">
            没有可读的 bundle(NOT_AVAILABLE)。依赖 bundle 的规则标为“未评估”,只评估了能由 Java 数据判断的规则。
          </p>
        )}
        {data.bundle.shape_failures && data.bundle.shape_failures.length > 0 ? (
          <div className="notice notice--error">
            <p>bundle 结构问题:</p>
            <ul>
              {data.bundle.shape_failures.map(f => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="rules-title">
        <h2 id="rules-title">12 条规则</h2>
        {data.rules.length === 0 ? (
          <EmptyView title="没有规则结果">BFF 没有返回任何规则。</EmptyView>
        ) : (
          <table className="table">
            <caption>发布前检查规则。DATA = 由 Java 数据判断;BUNDLE = 需要 bundle 才能判断。</caption>
            <thead>
              <tr>
                <th scope="col">规则</th>
                <th scope="col">名称</th>
                <th scope="col">依据</th>
                <th scope="col">结果</th>
                <th scope="col">详情</th>
              </tr>
            </thead>
            <tbody>
              {data.rules.map(rule => (
                <RuleRow key={rule.id} rule={rule} />
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

function PrecheckLoader({ workId }: { workId: string }) {
  const result = useAsync(signal => getPrecheck(workId, signal), [workId]);
  return (
    <AsyncView result={result} loadingLabel="正在评估规则…" errorTitle="发布前检查加载失败">
      {data => <PrecheckBody data={data} />}
    </AsyncView>
  );
}

export function PrecheckPage() {
  return (
    <>
      <PageHeader title="发布前检查" lead="只读清单。显示每条规则的依据与结果,不提供任何发布动作。" />
      <WorkScope>{work => <PrecheckLoader workId={work.work_id} />}</WorkScope>
    </>
  );
}
