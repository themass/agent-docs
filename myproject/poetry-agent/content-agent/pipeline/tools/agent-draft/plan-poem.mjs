#!/usr/bin/env node
/**
 * What an authoring run still has to produce, computed from the base instead of guessed.
 * This is the agent's first job: read the base, enumerate the gap, draft only DRAFT rows.
 *   node plan-poem.mjs --work work-chun-wang [--version text-chun-wang-draft]
 */
import { tools, assertAllowed } from './base-tools.mjs';
const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf('--' + n); return i >= 0 ? argv[i + 1] : d; };
const work = opt('work');
if (!work) { console.error('usage: node plan-poem.mjs --work <work-id>'); process.exit(2); }

const workRow = tools.content(work);
if (!workRow.length) { console.log(JSON.stringify({ work, exists: false,
  first_steps: ['content 行不存在：先建 poetry_content(entity_type=WORK) 草稿', '再建 source → text_version → text_line'] }, null, 2)); process.exit(0); }
const [id, entityType, title, status] = workRow[0].split('\t');
const versions = tools.versions(id).map(r => r.split('\t'));
const version = opt('version') || versions.find(v => v[2] === 'PUBLISHED')?.[0] || versions[0]?.[0] || null;
const lines = version ? tools.poemLines(version).map(r => r.split('\t')) : [];
const backgrounds = tools.backgrounds(id).map(r => r.split('\t'));
const links = tools.bgLineLinks(id).map(r => r.split('\t'));
const annotations = version ? tools.annotations(version).map(r => r.split('\t')) : [];
const claims = tools.claims(id).map(r => r.split('\t'));
const claimState = new Map();
for (const bg of backgrounds) for (const c of tools.claims(bg[0])) { const p = c.split('\t'); claimState.set(p[0], { id: p[0], bg: bg[0], kind: p[1], certainty: p[2], status: p[3], refs: Number(p[4]), verified: Number(p[5]) }); }

const layers = new Set(backgrounds.map(b => b[1]));
const gaps = [];
if (status !== 'PUBLISHED') gaps.push(`发布 ${title}（当前 ${status}）`);
if (!version) gaps.push('没有 text_version：先 source 后 version 后 line');
if (version && lines.length === 0) gaps.push(`${version} 没有 text_line`);
for (const layer of ['SCENE', 'CITY', 'WORLD', 'PERSON']) if (!layers.has(layer)) gaps.push(`缺 ${layer} 层背景`);
for (const bg of backgrounds) if (!links.some(l => l[0] === bg[0])) gaps.push(`${bg[0]}（${bg[1]}）没有绑定任何诗句：这是"资料堆砌"，编译 R11 会拦`);
for (const [, c] of claimState) {
  if (c.verified === 0) gaps.push(`${c.bg} 的依据 ${c.id} 没有可核查引用（citations=${c.refs} verified=0）`);
  if (c.status !== 'PUBLISHED') gaps.push(`${c.bg} 的依据仍是 ${c.status}`);
}
if (annotations.length < 4) gaps.push(`注释只有 ${annotations.length} 条：「回」步需要字词/意象/韵律至少 4 条`);

console.log(JSON.stringify({ work: id, title, status, version, lines: lines.length, layers: [...layers],
  claims: claimState.size, annotations: annotations.length, allowed_writes: 'DRAFT only', forbidden: ['publish', 'retract', 'verify'],
  gaps }, null, 2));
