#!/usr/bin/env node
/**
 * Builds a FIXTURE fact file: the real base's shape with the 春望 ids promoted to published.
 * It exists to exercise the compile + delivery pipeline without pretending the scholarship is done.
 * Anything compiled from it is labelled facts_source=fixture, end to end.
 */
import { readFileSync, writeFileSync } from 'node:fs';
const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf('--' + n); return i >= 0 ? argv[i + 1] : d; };
const facts = JSON.parse(readFileSync(opt('from', '../../contracts/facts.chun-wang.json'), 'utf8'));
const script = JSON.parse(readFileSync(opt('script', '../../contracts/sample.chun-wang.json'), 'utf8'));

const referenced = new Set();
const add = id => id && referenced.add(id);
add(script.work_id); add(script.text_version_id);
(script.annotation_ids || []).forEach(add);
for (const s of script.steps) {
  add(s.person_id); if (s.at) { add(s.at.place_id); add(s.at.year_claim); (s.at.year_claims || []).forEach(add); }
  const walk = layers => (layers || []).forEach(l => { add(l.bg_id); add(l.theme_id);
    (l.places || []).forEach(add); (l.events || []).forEach(add); (l.experience || []).forEach(add);
    (l.lines || []).forEach(x => x.basis && add(x.basis.claim_id)); });
  walk(s.layers); if (s.roleplay) walk(s.roleplay.layers);
  (s.text_side?.annotations || []).forEach(add);
}
for (const c of script.cast || []) add(c.content_id);

const out = {
  generated_by: 'FIXTURE — not from the database; the scholarship is still PENDING',
  published_ids: [...new Set([...facts.published_ids, ...referenced])].sort(),
  draft_ids: facts.draft_ids.filter(id => !referenced.has(id)),
  lines: facts.lines,
  cited_claim_ids: [...new Set([...facts.cited_claim_ids, ...[...referenced].filter(id => String(id).startsWith('claim-'))])].sort(),
  unknown_date_ids: facts.unknown_date_ids,
  background_line_counts: facts.background_line_counts,
};
writeFileSync(opt('out', '../../contracts/facts.fixture.json'), JSON.stringify(out, null, 2) + '\n');
console.error(`fixture facts: published=${out.published_ids.length} cited=${out.cited_claim_ids.length} (real base stays: published=${facts.published_ids.length} cited=${facts.cited_claim_ids.length})`);
