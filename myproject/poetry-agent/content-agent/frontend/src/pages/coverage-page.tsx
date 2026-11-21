import { useState } from 'react';
import { getCoverage, getGapReport } from '../api/client';
import type { Coverage, Gap, GapReport } from '../api/types';
import { AsyncView, EmptyView, ErrorView, LoadingView } from '../components/async-view';
import { Meter, PageHeader } from '../components/ui';
import { WorkScope } from '../components/work-scope';
import { LAYER_LABEL, LAYER_ORDER } from '../lib/labels';
import { useAsync, type AsyncResult } from '../lib/use-async';

const TOTAL_LABEL: Record<string, string> = {
  lines: '诗句',
  versions: '文本版本',
  backgrounds: '背景',
  annotations: '注释',
  claims: 'claim',
  sources: '来源',
  citations: '引用',
};

/** 数字 + 条形双重表达;条形所在的表格同时是读屏可读的“表格视图”。 */
function Distribution({ title, rows, total }: { title: string; rows: [string, number][]; total: number }) {
  return (
    <div className="dist">
      <table className="table table--compact">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">类别</th>
            <th scope="col" className="num">
              数量
            </th>
            <th scope="col" className="num">
              占比
            </th>
            <th scope="col">条形</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, count]) => {
            const pct = total > 0 ? Math.round((count / total) * 100) : 0;
            return (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td className="num">{count}</td>
                <td className="num">{pct}%</td>
                <td>
                  <span className="bar" aria-hidden="true">
                    <span className="bar__fill" style={{ width: `${pct}%` }} />
                  </span>
                  <span className="bar__text" aria-hidden="true">
                    {'█'.repeat(Math.round(pct / 10)) || '·'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function sum(record: Record<string, number>): number {
  return Object.values(record).reduce((a, b) => a + b, 0);
}

function LineMatrix({ coverage }: { coverage: Coverage }) {
  const [gapsOnly, setGapsOnly] = useState(false);
  const multiVersion = new Set(coverage.lines.map(l => l.version_id)).size > 1;
  const rows = coverage.lines.map(line => ({
    line,
    noAnnotation: line.annotation_count === 0,
    noBackground: line.background_count === 0,
  }));
  const shown = gapsOnly ? rows.filter(r => r.noAnnotation || r.noBackground) : rows;
  const gapCount = rows.filter(r => r.noAnnotation || r.noBackground).length;

  if (coverage.lines.length === 0) {
    return <EmptyView title="这个作品还没有诗句">没有文本版本或诗句,无法生成逐句覆盖矩阵。</EmptyView>;
  }
  return (
    <>
      <label className="check">
        <input type="checkbox" checked={gapsOnly} onChange={event => setGapsOnly(event.target.checked)} />
        只看有缺口的句子({gapCount} / {rows.length})
      </label>
      <table className="table">
        <caption>逐句覆盖矩阵:每句有几条注释、几条背景、命中哪几层</caption>
        <thead>
          <tr>
            {multiVersion ? <th scope="col">版本</th> : null}
            <th scope="col" className="num">
              句
            </th>
            <th scope="col">诗句</th>
            <th scope="col" className="num">
              注释
            </th>
            <th scope="col" className="num">
              背景
            </th>
            {LAYER_ORDER.map(layer => (
              <th scope="col" key={layer}>
                {LAYER_LABEL[layer]}
              </th>
            ))}
            <th scope="col">缺口</th>
          </tr>
        </thead>
        <tbody>
          {shown.map(({ line, noAnnotation, noBackground }) => (
            <tr key={`${line.version_id}#${line.line_seq}`}>
              {multiVersion ? <td>{line.version_id}</td> : null}
              <td className="num">{line.line_seq}</td>
              <th scope="row" className="poem-cell">
                {line.content}
              </th>
              <td className="num">{line.annotation_count}</td>
              <td className="num">{line.background_count}</td>
              {LAYER_ORDER.map(layer => (
                <td key={layer}>{line.layers.includes(layer) ? '● 有' : '○ 无'}</td>
              ))}
              <td>
                {noAnnotation || noBackground ? (
                  <ul className="flags">
                    {noAnnotation ? <li>△ 无注释</li> : null}
                    {noBackground ? <li>△ 无背景</li> : null}
                  </ul>
                ) : (
                  <span className="muted">✓ 无</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function GapList({ coverage, gaps }: { coverage: Coverage; gaps: AsyncResult<GapReport> }) {
  const merged = new Map<string, Gap[]>();
  const state = gaps.state;
  if (state.status === 'ready') {
    for (const gap of state.data.gaps) merged.set(gap.code, [...(merged.get(gap.code) ?? []), gap]);
  }
  const codes = [...new Set([...coverage.gap_codes, ...merged.keys()])];
  return (
    <section aria-labelledby="gaps-title">
      <h2 id="gaps-title">缺口代码</h2>
      {state.status === 'loading' ? <LoadingView label="正在加载缺口明细…" /> : null}
      {state.status === 'error' ? <ErrorView error={state.error} title="缺口明细加载失败" onRetry={gaps.reload} /> : null}
      {codes.length === 0 ? (
        <EmptyView title="没有缺口代码">
          Java 完整性报告没有列出缺口。这<strong>不等于</strong>可以发布,请继续看“发布前检查”。
        </EmptyView>
      ) : (
        <table className="table">
          <caption>缺口代码清单</caption>
          <thead>
            <tr>
              <th scope="col">代码</th>
              <th scope="col">严重度</th>
              <th scope="col">说明</th>
              <th scope="col">目标</th>
            </tr>
          </thead>
          <tbody>
            {codes.flatMap(code => {
              const details = merged.get(code);
              if (!details) {
                return [
                  <tr key={code}>
                    <th scope="row">
                      <code>{code}</code>
                    </th>
                    <td>—</td>
                    <td className="muted">明细未加载</td>
                    <td>—</td>
                  </tr>,
                ];
              }
              return details.map((gap, index) => (
                <tr key={`${code}-${index}`}>
                  <th scope="row">
                    <code>{code}</code>
                  </th>
                  <td>{gap.severity ?? '—'}</td>
                  <td>{gap.message ?? '—'}</td>
                  <td>{gap.target_ref ?? '—'}</td>
                </tr>
              ));
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}

function CoverageBody({ workId }: { workId: string }) {
  const coverage = useAsync(signal => getCoverage(workId, signal), [workId]);
  const gaps = useAsync(signal => getGapReport(workId, signal), [workId]);
  return (
    <AsyncView result={coverage} loadingLabel="正在加载覆盖数据…" errorTitle="覆盖数据加载失败">
      {data => {
        const claimsTotal = sum(data.claims_by_status);
        const sourcesTotal = sum(data.sources_by_verification);
        const checkable = data.claims_checkable;
        return (
          <>
            <section aria-labelledby="totals-title">
              <h2 id="totals-title">总量</h2>
              <ul className="totals">
                {Object.entries(data.totals).map(([key, value]) => (
                  <li key={key}>
                    <span className="totals__num num">{value}</span>
                    <span className="totals__label">{TOTAL_LABEL[key] ?? key}</span>
                  </li>
                ))}
              </ul>
              {data.publication ? (
                <p className="muted">
                  作品状态 <code>{data.publication.work_status ?? '—'}</code> · 已发布 claim {data.publication.published_claims ?? 0} · 审计检查{' '}
                  {data.publication.audit_checks ?? '—'} 项
                  {data.publication.audit_non_zero && data.publication.audit_non_zero.length > 0
                    ? `,其中 ${data.publication.audit_non_zero.length} 项非零`
                    : ',无非零项'}
                </p>
              ) : null}
            </section>

            <section aria-labelledby="dist-title">
              <h2 id="dist-title">claim 与来源</h2>
              <div className="dist-grid">
                <Distribution
                  title="claim 按状态"
                  total={claimsTotal}
                  rows={Object.entries(data.claims_by_status)}
                />
                <Distribution
                  title="来源按核验状态"
                  total={sourcesTotal}
                  rows={Object.entries(data.sources_by_verification)}
                />
              </div>
              <Meter
                label="可核查 claim(至少有一条真实 locator)"
                value={checkable.checkable}
                max={checkable.total}
                valueText={`${checkable.checkable} / ${checkable.total}`}
                warnAt={101}
              />
            </section>

            <section aria-labelledby="layers-title">
              <h2 id="layers-title">四层背景覆盖</h2>
              <table className="table table--compact">
                <caption>每层背景的条数,以及它们关联到多少句诗</caption>
                <thead>
                  <tr>
                    <th scope="col">层</th>
                    <th scope="col" className="num">
                      背景条数
                    </th>
                    <th scope="col" className="num">
                      关联诗句数
                    </th>
                    <th scope="col">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {LAYER_ORDER.map(layer => {
                    const item = data.layers[layer] ?? {};
                    const count = item.count ?? 0;
                    return (
                      <tr key={layer}>
                        <th scope="row">{LAYER_LABEL[layer]}</th>
                        <td className="num">{count}</td>
                        <td className="num">{item.linked_lines ?? 0}</td>
                        <td>{count === 0 ? '△ 这一层还没有背景' : (item.linked_lines ?? 0) === 0 ? '△ 有背景但没绑定诗句' : '● 已覆盖'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>

            <section aria-labelledby="matrix-title">
              <h2 id="matrix-title">逐句覆盖</h2>
              <LineMatrix coverage={data} />
            </section>

            <GapList coverage={data} gaps={gaps} />
          </>
        );
      }}
    </AsyncView>
  );
}

export function CoveragePage() {
  return (
    <>
      <PageHeader title="内容缺口与覆盖" lead="哪些句没有注释、哪些层没有背景、哪些 claim 还没有可核查出处。" />
      <WorkScope>{work => <CoverageBody workId={work.work_id} />}</WorkScope>
    </>
  );
}
