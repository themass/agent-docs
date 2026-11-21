#!/usr/bin/env node
/** TSV from facts-from-db.sh -> the facts JSON the validator reads. Zero dependencies. */
import { readFileSync, writeFileSync } from 'node:fs';

const tsv = readFileSync(process.argv[2] ?? '/dev/stdin', 'utf8');
const out = { published_ids: [], draft_ids: [], lines: [], cited_claim_ids: [],
              unknown_date_ids: [], background_line_counts: {} };
for (const row of tsv.split('\n')) {
  if (!row.trim()) continue;
  const [bucket, value] = row.split('\t');
  if (bucket === 'published') out.published_ids.push(value);
  else if (bucket === 'draft') out.draft_ids.push(value);
  else if (bucket === 'line') { const [version_id, seq] = value.split('#'); out.lines.push({ version_id, line_seq: Number(seq) }); }
  else if (bucket === 'cited_claim') out.cited_claim_ids.push(value);
  else if (bucket === 'unknown_date') out.unknown_date_ids.push(value);
  else if (bucket === 'bg_lines') { const [id, n] = value.split('#'); out.background_line_counts[id] = Number(n); }
}
for (const k of Object.keys(out)) if (Array.isArray(out[k])) out[k] = [...new Set(out[k])].sort();
writeFileSync(process.argv[3] ?? '/dev/stdout', JSON.stringify(out, null, 2) + '\n');
if (process.argv[3]) console.error(`published=${out.published_ids.length} draft=${out.draft_ids.length} lines=${out.lines.length} cited_claims=${out.cited_claim_ids.length} unknown_dates=${out.unknown_date_ids.length} bg_with_lines=${Object.keys(out.background_line_counts).length}`);
