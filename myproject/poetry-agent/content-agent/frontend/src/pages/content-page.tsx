import { useMemo, useState } from 'react';
import { getOverview } from '../api/client';
import type { StudioAnnotation, StudioBackground, StudioView } from '../api/types';
import { AsyncView, EmptyView } from '../components/async-view';
import { BasisLegend, BasisText } from '../components/trust';
import { Chip, ContentStatusMark, PageHeader } from '../components/ui';
import { WorkScope } from '../components/work-scope';
import { ANNOTATION_KIND_LABEL, CERTAINTY_LABEL, CLAIM_KIND_LABEL, LAYER_LABEL, LAYER_ORDER, labelOr } from '../lib/labels';
import { basisOfClaim, claimVerified, indexBy } from '../lib/trust';
import { useAsync } from '../lib/use-async';

function jumpTo(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ block: 'center' });
  el.focus();
}

function ContentBody({ view }: { view: StudioView }) {
  const claims = useMemo(() => indexBy(view.claims, c => c.id), [view.claims]);
  const versions = view.versions;
  const [versionId, setVersionId] = useState(versions[0]?.id ?? '');
  const version = versions.find(v => v.id === versionId) ?? versions[0];

  const workStatus = view.work?.status ?? view.content_status_by_id[view.work?.id ?? ''];
  const statusOfBackground = (b: StudioBackground) => view.content_status_by_id[b.id];
  const statusOfClaim = (claimId: string | null | undefined) => (claimId ? view.claim_status_by_id[claimId] : undefined);

  const lines = view.lines.filter(l => l.version_id === version?.id);
  const bgLinesByBg = useMemo(() => {
    const map = new Map<string, number[]>();
    for (const link of view.background_lines) {
      map.set(link.background_id, [...(map.get(link.background_id) ?? []), link.line_seq]);
    }
    return map;
  }, [view.background_lines]);
  const bgByLine = (seq: number) =>
    view.background_lines
      .filter(link => link.version_id === version?.id && link.line_seq === seq)
      .map(link => link.background_id);
  const annotationsByLine = (seq: number): StudioAnnotation[] =>
    view.annotations.filter(a => a.version_id === version?.id && a.line_seq === seq);

  const renderClaimText = (claimId: string | null | undefined, text: string) => {
    const claim = claimId ? claims.get(claimId) : undefined;
    const basis = basisOfClaim(claim);
    const verified = claimId ? claimVerified(claimId, view.citations) : false;
    return (
      <BasisText basis={basis} verified={verified}>
        {text}
      </BasisText>
    );
  };

  return (
    <>
      <section aria-labelledby="work-head" className="panel">
        <h2 id="work-head">
          {view.work?.title ?? view.work?.id ?? '作品'} <ContentStatusMark status={workStatus} />
        </h2>
        <p className="muted">
          草稿内容左侧有斜纹,已发布内容是实线,两者永久区分。史实、解释、演绎、不可考的标记含义见下方图例。
        </p>
        <BasisLegend />
      </section>

      <section aria-labelledby="lines-title">
        <h2 id="lines-title">诗句与注释</h2>
        {versions.length > 1 ? (
          <div className="toolbar">
            <label htmlFor="version-picker" className="toolbar__label">
              文本版本
            </label>
            <select id="version-picker" value={version?.id} onChange={e => setVersionId(e.target.value)}>
              {versions.map(v => (
                <option key={v.id} value={v.id}>
                  {v.label ?? v.version_code ?? v.id}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        {version ? (
          <p className="muted">
            版本 <code>{version.id}</code> <ContentStatusMark status={view.version_status_by_id[version.id] ?? version.status} />
            {version.source_locator ? ` · 来源定位 ${version.source_locator}` : ' · 版本来源定位缺失'}
          </p>
        ) : null}
        {lines.length === 0 ? (
          <EmptyView title="这个版本没有诗句">没有可展示的诗句。</EmptyView>
        ) : (
          <ol className="lines">
            {lines.map(line => {
              const annotations = annotationsByLine(line.line_seq);
              const bgIds = bgByLine(line.line_seq);
              return (
                <li key={`${line.version_id}-${line.line_seq}`} className="line" data-status={view.version_status_by_id[line.version_id]}>
                  <div className="line__head">
                    <span className="line__seq num">{line.line_seq}</span>
                    <span className="poem-line line__text">{line.content}</span>
                    {line.pinyin ? <span className="line__pinyin">{line.pinyin}</span> : null}
                  </div>
                  <div className="line__links">
                    {bgIds.length > 0 ? (
                      bgIds.map(id => (
                        <button type="button" key={id} className="link-chip" onClick={() => jumpTo(`bg-${id}`)}>
                          背景:{view.backgrounds.find(b => b.id === id)?.layer ? LAYER_LABEL[view.backgrounds.find(b => b.id === id)!.layer] : id}
                        </button>
                      ))
                    ) : (
                      <span className="basis-text basis-text--unknown">这一句暂时没有关联背景</span>
                    )}
                  </div>
                  {annotations.length === 0 ? (
                    <p className="basis-text basis-text--unknown line__empty">这一句暂时没有注释(不可考/待补)</p>
                  ) : (
                    <ul className="annotations">
                      {annotations.map(a => (
                        <li key={a.id} className="annotation" data-status={statusOfClaim(a.claim_id)}>
                          <span className="annotation__kind">
                            {labelOr(ANNOTATION_KIND_LABEL, a.annotation_kind)}
                            {a.audience ? ` · ${a.audience}` : ''}
                          </span>
                          {renderClaimText(a.claim_id, a.content ?? '')}
                          {a.claim_id ? (
                            <span className="claim-meta">
                              {' '}
                              {labelOr(CERTAINTY_LABEL, claims.get(a.claim_id)?.certainty)}
                            </span>
                          ) : null}
                          <ContentStatusMark status={statusOfClaim(a.claim_id)} />
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </section>

      <section aria-labelledby="bg-title">
        <h2 id="bg-title">四层背景</h2>
        {view.backgrounds.length === 0 ? (
          <EmptyView title="这个作品还没有背景">四层背景(眼前/这座城/这个天下/这个人)都为空。</EmptyView>
        ) : (
          LAYER_ORDER.map(layer => {
            const items = view.backgrounds.filter(b => b.layer === layer);
            return (
              <div key={layer} className="layer">
                <h3>{LAYER_LABEL[layer]}</h3>
                {items.length === 0 ? (
                  <p className="basis-text basis-text--unknown">这一层暂时没有背景(不可考/待补)</p>
                ) : (
                  <ul className="backgrounds">
                    {items.map(b => {
                      const seqs = bgLinesByBg.get(b.id) ?? [];
                      return (
                        <li key={b.id} id={`bg-${b.id}`} tabIndex={-1} className="background" data-status={statusOfBackground(b)}>
                          <div className="background__head">
                            <ContentStatusMark status={statusOfBackground(b)} />
                            {b.audience ? <span className="muted">受众 {b.audience}</span> : null}
                          </div>
                          <p className="prose">{renderClaimText(b.claim_id, b.body_text ?? '')}</p>
                          <p className="muted">
                            {seqs.length > 0
                              ? `关联诗句:第 ${[...seqs].sort((x, y) => x - y).join('、')} 句`
                              : '这条背景暂时没有绑定诗句'}
                          </p>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            );
          })
        )}
      </section>

      <section aria-labelledby="claims-title">
        <h2 id="claims-title">claim 与引用</h2>
        {view.claims.length === 0 ? (
          <EmptyView title="这个作品还没有 claim">没有 claim,也就没有可核查的出处。</EmptyView>
        ) : (
          <table className="table">
            <caption>每条 claim 的类型、确定度、状态与出处</caption>
            <thead>
              <tr>
                <th scope="col">claim</th>
                <th scope="col">内容</th>
                <th scope="col">类型 / 确定度</th>
                <th scope="col">状态</th>
                <th scope="col">引用</th>
              </tr>
            </thead>
            <tbody>
              {view.claims.map(claim => {
                const cites = view.citations.filter(c => c.claim_id === claim.id);
                const status = view.claim_status_by_id[claim.id] ?? claim.status;
                return (
                  <tr key={claim.id} data-status={status}>
                    <th scope="row">
                      <code>{claim.id}</code>
                      <span className="muted block">{claim.property_key}</span>
                    </th>
                    <td>{renderClaimText(claim.id, claim.value_text ?? '')}</td>
                    <td>
                      {labelOr(CLAIM_KIND_LABEL, claim.claim_kind)}
                      <span className="muted block">{labelOr(CERTAINTY_LABEL, claim.certainty)}</span>
                    </td>
                    <td>
                      <ContentStatusMark status={status} />
                    </td>
                    <td>
                      {cites.length === 0 ? (
                        <span className="basis-text basis-text--unknown">无引用(不可考/待核)</span>
                      ) : (
                        <ul className="plain-list">
                          {cites.map(c => {
                            const src = view.sources.find(s => s.id === c.source_id);
                            const verified = c.verification_status === 'VERIFIED' && (c.locator ?? '').trim() !== '';
                            return (
                              <li key={`${c.claim_id}-${c.source_id}`}>
                                <Chip
                                  tone={verified ? 'done' : 'review'}
                                  glyph={verified ? '✓' : '◇'}
                                  label={verified ? '已核验' : c.verification_status === 'VERIFIED' ? '缺 locator' : '来源待核'}
                                />{' '}
                                {src?.title ?? c.source_id}
                                <span className="muted block">
                                  {(c.locator ?? '').trim() !== '' ? `locator:${c.locator}` : 'locator:待核'}
                                  {c.evidence_excerpt ? ` · 摘录:${c.evidence_excerpt}` : ''}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

function ContentLoader({ workId }: { workId: string }) {
  const result = useAsync(signal => getOverview(workId, signal), [workId]);
  return (
    <AsyncView result={result} loadingLabel="正在加载作品内容…" errorTitle="作品内容加载失败">
      {view => <ContentBody view={view} />}
    </AsyncView>
  );
}

export function ContentPage() {
  return (
    <>
      <PageHeader title="作品内容" lead="四层背景、逐句注释、claim 与引用。草稿与已发布永久区分,史实/解释/演绎/不可考一眼可辨。" />
      <WorkScope>{work => <ContentLoader workId={work.work_id} />}</WorkScope>
    </>
  );
}
