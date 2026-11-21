import { tools, assertAllowed } from '../../../pipeline/tools/agent-draft/base-tools.mjs';

export function readBase(workId, versionId = null) {
  assertAllowed('content');
  const work = tools.content(workId);
  if (!work.length) return { exists: false, workId };
  const [id, entityType, title, status] = work[0].split('\t');
  const versions = tools.versions(id).map(row => row.split('\t'));
  const version = versionId || versions.find(v => v[2] === 'PUBLISHED')?.[0] || versions[0]?.[0] || null;
  return {
    exists: true, work: { id, entityType, title, status },
    versions: versions.map(([versionId, versionCode, versionStatus]) => ({ id: versionId, code: versionCode, status: versionStatus })),
    versionId: version,
    lines: version ? tools.poemLines(version).map(row => { const [line_seq, content] = row.split('\t'); return { line_seq: Number(line_seq), content }; }) : [],
    backgrounds: tools.backgrounds(id).map(row => { const [bgId, layer, audience, body] = row.split('\t'); return { id: bgId, layer, audience, body }; }),
    links: tools.bgLineLinks(id).map(row => { const [background_id, line_seq] = row.split('\t'); return { background_id, line_seq: Number(line_seq) }; }),
    annotations: version ? tools.annotations(version).map(row => { const [id, line_seq, annotation_kind, body] = row.split('\t'); return { id, line_seq: Number(line_seq), annotation_kind, body }; }) : [],
    claims: tools.claims(id).map(row => { const [id, claim_kind, certainty, claimStatus, citations, verified_refs] = row.split('\t'); return { id, claim_kind, certainty, status: claimStatus, citations: Number(citations), verified_refs: Number(verified_refs) }; })
  };
}
