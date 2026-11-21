export function makeProposal(base) {
  if (!base.exists) return { status: 'DRAFT', work_id: base.workId, gaps: ['content 行不存在：先创建 WORK 草稿'], text_version_id: null, claims: [], annotations: [], backgrounds: [], citation_requests: [], unsupported_items: [], compile_result: { verdict: 'NOT_RUN', failures: ['base_not_found'] } };
  const gaps = [];
  if (base.work.status !== 'PUBLISHED') gaps.push(`发布 ${base.work.title}（当前 ${base.work.status}）`);
  if (!base.versionId) gaps.push('没有 text_version：先 source → version → line');
  if (base.versionId && base.lines.length === 0) gaps.push(`${base.versionId} 没有 text_line`);
  const layers = new Set(base.backgrounds.map(b => b.layer));
  for (const layer of ['SCENE', 'CITY', 'WORLD', 'PERSON']) if (!layers.has(layer)) gaps.push(`缺 ${layer} 层背景`);
  for (const bg of base.backgrounds) if (!base.links.some(link => link.background_id === bg.id)) gaps.push(`${bg.id} 没有绑定任何诗句`);
  for (const claim of base.claims) {
    if (claim.verified_refs === 0) gaps.push(`${claim.id} 没有可核查引用`);
    if (claim.status !== 'PUBLISHED') gaps.push(`${claim.id} 仍是 ${claim.status}`);
  }
  if (base.annotations.length < 4) gaps.push(`注释只有 ${base.annotations.length} 条，回步至少需要 4 条`);
  return {
    status: 'DRAFT', work_id: base.work.id, text_version_id: base.versionId, gaps,
    claims: [], annotations: [], backgrounds: [],
    citation_requests: base.claims.filter(c => c.verified_refs === 0).map(c => ({ claim_id: c.id, reason: '需要人工核查出处' })),
    unsupported_items: ['出处核查、史实断言和发布状态不能由 Agent 自动确认'],
    compile_result: { verdict: 'NOT_RUN', failures: ['proposal_only'] }
  };
}
