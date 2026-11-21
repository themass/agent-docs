#!/usr/bin/env node
/** TSV from preview-content.sh -> apps/web/public/preview.json (internal preview feed, draft-labelled). */
import { readFileSync, writeFileSync } from 'node:fs';
const tsv = readFileSync(process.argv[2] ?? '/dev/stdin', 'utf8');
const out = { work_id: 'work-chun-wang', text_version_id: 'text-chun-wang-draft',
              lines: [], annotations: [], backgrounds: [], relations: [], coverage: [], status: {}, fetched_at: new Date().toISOString() };
for (const row of tsv.split('\n')) {
  if (!row.trim()) continue;
  const [bucket, raw] = row.split('\t');
  const p = raw.split('#');
  if (bucket === 'line') out.lines.push({ seq: Number(p[0]), text: p.slice(1).join('#') });
  if (bucket === 'annotation') out.annotations.push({ lineSeq: Number(p[0]), kind: p[1], audience: p[2], id: p[3], text: p.slice(4).join('#') });
  if (bucket === 'background') out.backgrounds.push({ layer: p[0], id: p[1], body: p.slice(2).join('#') });
  if (bucket === 'relation') out.relations.push({ backgroundId: p[0], versionId: p[1], lineSeq: Number(p[2]) });
  if (bucket === 'coverage') out.coverage.push({ id: p[0], entityType: p[1], fromYear: Number(p[2]), toYear: Number(p[3]), kind: p[4], status: p[5] });
  if (bucket === 'status') out.status[p[0]] = p[1];
}
out.lines.sort((a, b) => a.seq - b.seq);
writeFileSync(process.argv[3], JSON.stringify(out, null, 2) + '\n');
console.error(`lines=${out.lines.length} annotations=${out.annotations.length} backgrounds=${out.backgrounds.length} relations=${out.relations.length} coverage=${out.coverage.length}`);
