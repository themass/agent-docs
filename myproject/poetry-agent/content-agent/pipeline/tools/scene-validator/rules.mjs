/**
 * The 12 compile rules, importable. validate.mjs is the CLI; the scene compiler calls this before
 * it will write a single byte of a bundle. One definition, two entry points.
 */
const STEPS = ['read', 'arrive', 'meet', 'return', 'recite'];
const LAYERS = ['SCENE', 'CITY', 'WORLD', 'PERSON'];
const KINDS = ['FACT', 'INTERPRETATION', 'DRAMATIZATION'];
const LEVELS = ['L0', 'L1', 'L2', 'L3', 'L4'];
const TERMINAL = 'L0-text';

/* Rules that need no base facts. The other six (R1 R2 R6 R7 R8 R11) read the base and run only with facts. */
const RULES_WITHOUT_FACTS = ['R0', 'R3', 'R4', 'R5', 'R9', 'R10', 'R12'];
const RULES_NEEDING_FACTS = ['R1', 'R2', 'R6', 'R7', 'R8', 'R11'];

/* Pure function: no argv, no process.exit, no I/O. The CLI lives in validate.mjs.
 * Returns the rule ids that actually ran, so callers never record a count they did not execute. */
export function checkRules(bundle, facts) {
const fail = [];
const warn = [];
const skippedRules = new Set();
const rule = (id, name) => `${id} ${name}`;
const need = (cond, r, msg) => { if (!cond) fail.push(`${r}: ${msg}`); };
const published = new Set(facts ? facts.published_ids : []);
const drafts = new Set(facts ? facts.draft_ids : []);
const citedClaims = new Set(facts ? facts.cited_claim_ids || [] : []);
const unknownDates = new Set(facts ? facts.unknown_date_ids || [] : []);
const bgLineCounts = (facts && facts.background_line_counts) || {};
const linesOf = new Map();
if (facts) for (const l of facts.lines || []) {
  const key = String(l.version_id), seq = Number(l.line_seq);
  if (!linesOf.has(key)) linesOf.set(key, []);
  linesOf.get(key).push(seq);
}

/* ---------- structural walk (single source of truth for "everything a bundle touches") ---------- */
function layersOf(step) {
  const out = [];
  if (Array.isArray(step.layers)) out.push(...step.layers);
  if (step.roleplay && Array.isArray(step.roleplay.layers)) out.push(...step.roleplay.layers);
  if (Array.isArray(step.branches)) for (const b of step.branches) out.push(...layersOf(b));
  return out;
}
const allLayers = (bundle.steps || []).flatMap(layersOf);
const allLines = allLayers.flatMap(l => l.lines || []);

/* ---------- R0 shape ---------- */
for (const key of ['schema_version', 'script_id', 'script_version', 'work_id', 'text_version_id',
                   'audiences', 'coverage_notice', 'steps', 'assets'])
  need(bundle[key] !== undefined, rule('R0', 'shape'), `missing "${key}"`);
if (!Array.isArray(bundle.steps) || bundle.steps.length === 0)
  fail.push(`${rule('R0', 'shape')}: steps must be a non-empty array`);
need(String(bundle.schema_version || '').split('.')[0] === '1', rule('R0', 'shape'),
  `schema_version ${bundle.schema_version} is outside the 1.x range this runtime supports`);

/* ---------- R0 step / R12 free movement ---------- */
for (const step of bundle.steps || []) {
  need(STEPS.includes(step.step), rule('R0', 'step'), `unknown step "${step.step}"`);
  need(step.skip_allowed === true, rule('R12', 'free movement'),
    `${step.step} must set skip_allowed:true — no step may gate the next one`);
  need(step.back_allowed === true, rule('R12', 'free movement'),
    `${step.step} must set back_allowed:true — a learner must always be able to go back`);
}
const seenSteps = new Set((bundle.steps || []).map(s => s.step));
for (const s of STEPS) if (!seenSteps.has(s))
  warn.push(`${rule('R0', 'step')}: no "${s}" step in this bundle`);

/* ---------- R5 coverage is never optional ---------- */
need(typeof bundle.coverage_notice === 'string' && bundle.coverage_notice.trim().length >= 12,
  rule('R5', 'coverage declared'),
  'coverage_notice is required and must say what this round does NOT cover');

/* ---------- collect every base id the bundle touches ---------- */
const baseIds = new Set([bundle.work_id, bundle.text_version_id]);
for (const c of bundle.cast || []) {
  baseIds.add(c.content_id);
  if (c.avatar_asset) (bundle.assets ||= {})[c.avatar_asset] && baseIds.delete(c.avatar_asset);
}
for (const step of bundle.steps || []) {
  if (step.person_id) baseIds.add(step.person_id);
  if (step.at) {
    baseIds.add(step.at.place_id);
    for (const c of [step.at.year_claim, ...(step.at.year_claims || [])]) baseIds.add(c);
  }
  for (const l of layersOf(step)) {
    baseIds.add(l.bg_id);
    if (l.theme_id) baseIds.add(l.theme_id);
    for (const arr of [l.places, l.events, l.experience]) for (const id of arr || []) baseIds.add(id);
  }
}
for (const id of (bundle.annotation_ids || [])) baseIds.add(id);
for (const step of bundle.steps || []) for (const a of step.text_side?.annotations || []) baseIds.add(a);
for (const id of [...baseIds]) if (id === undefined || id === null) baseIds.delete(id);

/* ---------- R1 / R2 references exist and are published ---------- */
if (!facts) {
  skippedRules.add(rule('R1', 'reference exists'));
  skippedRules.add(rule('R2', 'published only'));
  skippedRules.add(rule('R7', 'annotations from base'));
  skippedRules.add(rule('R8', 'line link'));
  skippedRules.add(rule('R11', 'no pile-up'));
  skippedRules.add(rule('R6', 'unknown dates'));
} else {
  for (const id of baseIds) {
    need(published.has(id) || drafts.has(id), rule('R1', 'reference exists'),
      `${id} does not exist in the base at all`);
    need(published.has(id), rule('R2', 'published only'),
      `${id} is not PUBLISHED — unpublished content must never reach a student`);
  }
  /* ---------- R7 annotations come from the base, never written into the page ---------- */
  need(bundle.glossary_bindings === true, rule('R7', 'annotations from base'),
    'glossary_bindings must be true');
  for (const id of [...(bundle.annotation_ids || []),
                    ...(bundle.steps || []).flatMap(s => s.text_side?.annotations || [])])
    need(published.has(id), rule('R7', 'annotations from base'), `annotation ${id} is not published`);
  /* ---------- R6 unknown dates must be declared, never hidden ---------- */
  const uncertain = [...baseIds].filter(id => unknownDates.has(id));
  if (uncertain.length)
    need(typeof bundle.unknown_dates_notice === 'string' && bundle.unknown_dates_notice.trim().length >= 6,
      rule('R6', 'unknown dates'),
      `references uncertain dates (${uncertain.join(', ')}) but declares no unknown_dates_notice`);
  /* ---------- R8 background->line links must land on real lines ---------- */
  const seqs = linesOf.get(String(bundle.text_version_id)) || [];
  for (const l of allLayers) for (const seq of l.line_seqs || [])
    need(seqs.includes(Number(seq)), rule('R8', 'line link'),
      `${l.bg_id} links to line ${seq}, which does not exist in ${bundle.text_version_id}`);
  /* ---------- R11 no orphan background (anti pile-up) ---------- */
  for (const l of allLayers)
    need(Number(bgLineCounts[l.bg_id] || 0) > 0, rule('R11', 'no pile-up'),
      `${l.bg_id} is bound to no line in the base: background that cannot explain a line is pile-up, not teaching`);
}

/* ---------- R3 every spoken line carries a basis, or is visibly dramatisation ---------- */
for (const step of bundle.steps || []) {
  if (step.roleplay) need(step.roleplay.declared_as === 'DRAMATIZATION', rule('R3', 'basis'),
    `${step.step}: roleplay must declare declared_as:"DRAMATIZATION" — the product rule is visible labelling`);
}
for (const line of allLines) {
  const tag = `"${String(line.text || '').slice(0, 14)}"`;
  need(KINDS.includes(line.kind), rule('R3', 'basis'), `line ${tag} has no claim_kind`);
  if (line.kind === 'DRAMATIZATION') {
    // OQ-01（2026-11-11 定）：演绎只有一句固定的话。角标必须逐字与界面一致，
    // 否则同一个产品在不同位置对同一件事说不同的话。
    need(typeof line.badge === 'string' && line.badge.trim().length >= 2, rule('R3', 'basis'),
      `dramatisation ${tag} must carry a visible badge`);
    need(typeof line.badge === 'string' && line.badge.trim() === '演绎 · 不是史料', rule('R3', 'basis'),
      `dramatisation ${tag} badge must read 「演绎 · 不是史料」 verbatim — the wording is fixed by OQ-01`);
  } else {
    need(line.basis && line.basis.claim_id, rule('R3', 'basis'),
      `line ${tag} states ${line.kind} with no claim_id — an unattributed assertion`);
    if (facts && line.basis?.claim_id) {
      need(published.has(line.basis.claim_id), rule('R3', 'basis'),
        `claim ${line.basis.claim_id} is not published`);
      need(citedClaims.has(line.basis.claim_id), rule('R3', 'basis'),
        `claim ${line.basis.claim_id} has no checkable citation (VERIFIED source + real locator)`);
    }
  }
}

/* ---------- R4 every asset has a fallback chain that terminates at text ---------- */
const assets = bundle.assets || {};
for (const [id, a] of Object.entries(assets)) {
  need(LEVELS.includes(a.level), rule('R4', 'fallback'), `${id} has no media level`);
  let cursor = a, depth = 0;
  while (cursor && cursor.fallback && cursor.fallback.length && depth++ < 10) {
    const nextId = cursor.fallback[0];
    const next = assets[nextId];
    if (!next) {
      need(nextId === TERMINAL, rule('R4', 'fallback'),
        `${id}: chain reaches "${nextId}", which is neither a declared asset nor ${TERMINAL}`);
      cursor = null;
      break;
    }
    cursor = next;
    if (depth >= 10) { fail.push(`${rule('R4', 'fallback')}: ${id} fallback chain loops`); cursor = null; }
  }
  need(cursor === null, rule('R4', 'fallback'), `${id} has no path down to ${TERMINAL}`);
  /* ---------- R9 hash / R10 rights + meaning ---------- */
  need(typeof a.hash === 'string' && /^[a-f0-9]{12,64}$/.test(a.hash), rule('R9', 'hash'),
    `${id} has no content hash (content-addressed delivery is how offline + rollback work)`);
  need(a.rights && a.rights.origin && a.rights.license, rule('R10', 'rights'),
    `${id} has no provenance/licence — it cannot be shipped or re-made later`);
  need(typeof a.meaning === 'string' && a.meaning.trim().length >= 8, rule('R10', 'meaning'),
    `${id} cannot say which line it helps the student understand — so it should not exist`);
}
for (const l of allLayers) for (const ref of l.assets || [])
  need(assets[ref], rule('R4', 'asset declared'), `${l.layer} references asset "${ref}" that is not declared`);
for (const c of bundle.cast || []) {
  if (c.avatar_asset) need(assets[c.avatar_asset], rule('R4', 'asset declared'),
    `cast ${c.content_id} references avatar "${c.avatar_asset}" that is not declared`);
  if (c.voice_id) need(assets[c.voice_id], rule('R4', 'asset declared'),
    `cast ${c.content_id} references voice "${c.voice_id}" that is not declared`);
}
for (const step of bundle.steps || [])
  if (step.demo_audio) need(assets[step.demo_audio], rule('R4', 'asset declared'),
    `${step.step}: demo_audio "${step.demo_audio}" is not declared`);

/* ---------- report ---------- */
  const executed = facts ? [...RULES_WITHOUT_FACTS, ...RULES_NEEDING_FACTS].sort() : [...RULES_WITHOUT_FACTS];
  const skipped = facts ? [] : [...RULES_NEEDING_FACTS];
  return { failures: [...new Set(fail)], warnings: warn, executed, skipped, skippedDetail: [...skippedRules] };
}
