#!/usr/bin/env node
// 素材任务体系命令行。零依赖、零网络、不碰数据库、不调用 git。
//   node tools/prod.mjs gen <poem>                      生成/刷新任务单(tasks.json + sheets/*.md + INDEX.md),不冲掉 state.json
//   node tools/prod.mjs list <poem>                     任务与状态
//   node tools/prod.mjs state <poem> <task> <to> --by X [--assignee Y] [--note ...]
//   node tools/prod.mjs init-delivery <poem> <task>     在 inbox/<task>/ 建 delivery.json 模板
//   node tools/prod.mjs check <poem> <task> [--dry]     机检交付物;通过→AUTO_PASSED,不通过→REJECTED(--dry 只看结果)
//   node tools/prod.mjs publish <poem> <task>           HUMAN_ACCEPTED 的真素材入库 published/ 并登记
//   node tools/prod.mjs placeholder <poem> [task...]    机检并登记占位素材(not_for_release;不改任务状态)
//   node tools/prod.mjs registry-check                  检查 published/registry.json
//   node tools/prod.mjs bundle-refs <poem> [--channel production]  生成 published/bundles/<poem>.assets.json(给 bundle 的素材引用;--channel production 时只要含占位/缺素材就失败)
//   node tools/prod.mjs report [poem...]                进度报告(stdout + reports/progress.md)
import { readFileSync, writeFileSync, mkdirSync, copyFileSync, existsSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { PRODUCTION_ROOT, PUBLISHED, REGISTRY_PATH, levelRank, loadRegistry, saveRegistry, upsert, checkRegistry, describeFiles, fingerprint, readJson } from './lib/registry.mjs';
import { buildTasks, checkTasks, taskDir, loadState, saveState, ensureState, transition, renderMarkdown, listPoems, takenElsewhere } from './lib/tasks.mjs';
import { checkDelivery, parseVtt } from './lib/checks.mjs';
import { checkCharacter } from './character-check.mjs';

const [cmd, ...rest] = process.argv.slice(2);
const VALUE_FLAGS = new Set(['--by', '--assignee', '--note', '--channel']);
const pos = rest.filter((a, i) => !a.startsWith('--') && !VALUE_FLAGS.has(rest[i - 1]));
const flag = (k) => { const i = rest.indexOf(`--${k}`); return i >= 0 ? rest[i + 1] : undefined; };
const has = (k) => rest.includes(`--${k}`);
const die = (m, c = 1) => { console.error(m); process.exit(c); };
const norm = (s) => s.replace(/\s+/g, '');
const inboxDir = (id) => join(PRODUCTION_ROOT, 'inbox', id);

const poemTasks = (poem) => { const { tasks, warnings, demand, bundle } = buildTasks(poem); return { tasks, warnings, demand, bundle }; };
const findTask = (tasks, id) => tasks.find((t) => t.task_id === id) || die(`没有任务 ${id}`);

/** 文字类交付物必须与任务单脚本逐字一致。音频无法自动核对,留给人工。 */
export function scriptMatchErrors(task, dir, files) {
  const script = task.brief.script_text; if (!script) return [];
  const errs = [];
  for (const f of files) {
    if (f.path.endsWith('.vtt')) {
      const text = parseVtt(readFileSync(join(dir, f.path), 'utf8')).cues.map((c) => c.text).join('');
      if (norm(text) !== norm(script)) errs.push(`${f.path}: 字幕文字与任务单脚本不一致`);
    } else if (f.path.endsWith('.txt') && ['entry', 'script'].includes(f.role)) {
      if (norm(readFileSync(join(dir, f.path), 'utf8')) !== norm(script)) errs.push(`${f.path}: 文本与任务单脚本不一致`);
    }
  }
  return errs;
}

function fullCheck(task, dir) {
  const r = checkDelivery(task, dir);
  r.errors.push(...scriptMatchErrors(task, dir, r.files));
  if (task.kind === 'character' && existsSync(join(dir, 'manifest.json'))) {
    const c = checkCharacter(join(dir, 'manifest.json'));
    r.errors.push(...c.errors.map((e) => `角色清单: ${e}`)); r.warnings.push(...c.warnings);
  }
  return r;
}

/** 复制交付物进 published 并登记。placeholder=true 时以 not_for_release 登记。 */
function ingest(task, dir, r, { placeholder, scriptId }) {
  const dest = task.registry ? join(PUBLISHED, 'assets', task.asset_id) : join(PUBLISHED, 'resources', task.asset_id);
  rmSync(dest, { recursive: true, force: true });
  for (const f of r.files) { const to = join(dest, f.path); mkdirSync(dirname(to), { recursive: true }); copyFileSync(join(dir, f.path), to); }
  if (!task.registry) {
    const p = join(PUBLISHED, 'resources.json');
    const res = existsSync(p) ? readJson(p) : { schema_version: '1.0', resources: [] };
    const files = describeFiles(dest, r.files.map((f) => f.path));
    res.resources = res.resources.filter((x) => x.resource_id !== task.asset_id);
    res.resources.push({ resource_id: task.asset_id, type: task.type, files, rights: r.delivery.rights, task_id: task.task_id, published_at: new Date().toISOString() });
    writeFileSync(p, JSON.stringify(res, null, 2) + '\n');
    return { resource: true };
  }
  const roleOf = Object.fromEntries(r.files.map((f) => [f.path, f.role]));
  const files = describeFiles(dest, r.files.map((f) => f.path)).map((f) => {
    const rel = f.path.slice(`assets/${task.asset_id}/`.length);
    return { ...f, role: roleOf[rel] === 'layer' ? 'layer' : roleOf[rel] || 'entry' };
  });
  const entryFile = files.find((f) => f.role === 'entry') || files[0];
  const facts = r.files.find((f) => f.role === 'entry')?.facts || {};
  const media = Object.fromEntries(Object.entries({ width: facts.width, height: facts.height, duration_ms: facts.durationMs, sample_rate: facts.sampleRate, channels: facts.channels, cues: facts.cues }).filter(([, v]) => v !== undefined));
  const dr = r.delivery.rights; // registry 的 rights 只允许 origin/license/workflow/human_fix/author/notes;证明材料与第三方并入 notes
  const rights = Object.fromEntries(['origin', 'license', 'workflow', 'human_fix', 'author'].filter((k) => dr[k] !== undefined && dr[k] !== '').map((k) => [k, dr[k]]));
  const notes = [dr.notes, dr.evidence?.length ? `证明材料:${dr.evidence.join('、')}` : null, dr.third_party?.length ? `第三方:${dr.third_party.join('、')}` : null].filter(Boolean).join(';');
  if (notes) rights.notes = notes;
  const used = [...new Set(task.usage.steps.filter((s) => s !== 'all'))].map((step) => ({ ...(scriptId ? { script_id: scriptId } : {}), step }));
  const entry = {
    asset_id: task.asset_id, kind: task.kind, level: task.level, uri: entryFile.path, ...fingerprint(files), files, ...(Object.keys(media).length ? { media } : {}),
    render: task.render, rights, meaning: task.usage.purpose.trim(), fallback_asset_id: task.fallback.fallback_asset_id, status: 'published',
    placeholder: placeholder ? { is_placeholder: true, not_for_release: true, reason: '代码生成的占位,为了让学生端先跑通;不可上线', replace_with_task: task.task_id } : { is_placeholder: false, not_for_release: false },
    depiction: task.brief.depiction, task_id: task.task_id, ...(used.length ? { used_in: used } : {}),
    published_at: new Date().toISOString(), published_by: placeholder ? 'placeholder-pipeline' : undefined,
  };
  if (!entry.published_by) delete entry.published_by;
  const reg = loadRegistry(); upsert(reg, entry);
  const chk = checkRegistry(reg);
  if (chk.errors.length) { rmSync(dest, { recursive: true, force: true }); die('登记检查未通过(未写入 registry):\n' + chk.errors.map((e) => '  ✗ ' + e).join('\n')); }
  saveRegistry(reg);
  return { entry };
}

const commands = {
  gen(poem) {
    const { tasks, warnings, demand, bundle } = poemTasks(poem);
    const chk = checkTasks(tasks, bundle);
    const taken = takenElsewhere(poem);
    for (const t of tasks) if (taken.has(t.task_id)) chk.errors.push(`${t.task_id}: 与 tasks/${taken.get(t.task_id)} 的任务 id 冲突(inbox/ 与 published/assets/ 是按 id 平铺的全局命名空间)`);
    chk.errors.forEach((e) => console.error('✗', e));
    if (chk.errors.length) die(`任务单有 ${chk.errors.length} 个错误,未写入`);
    const st = ensureState(loadState(poem), tasks);
    for (const t of tasks) { // 脚本文本变了 → 提示任务单过期
      const prev = st.tasks[t.task_id].script_sha256;
      if (prev && t.brief.script_text_sha256 && prev !== t.brief.script_text_sha256 && st.tasks[t.task_id].state !== 'TODO') warnings.push(`${t.task_id}: bundle 文本已变,已派发/交付的素材需要按新脚本重做`);
      if (t.brief.script_text_sha256) st.tasks[t.task_id].script_sha256 = t.brief.script_text_sha256;
    }
    saveState(poem, st);
    const dir = taskDir(poem); mkdirSync(join(dir, 'sheets'), { recursive: true });
    writeFileSync(join(dir, 'tasks.json'), JSON.stringify({ schema_version: '1.0', poem, title: demand.title, generated_by: 'tools/prod.mjs gen', tasks }, null, 2) + '\n');
    const reg = loadRegistry(); const regOf = (id) => reg.assets.find((a) => a.asset_id === id);
    for (const t of tasks) writeFileSync(join(dir, 'sheets', `${t.task_id}.md`), renderMarkdown(t, st.tasks[t.task_id], regOf(t.asset_id)));
    const idx = ['# ' + demand.title + ' 素材任务总表', '', '> 由 `node tools/prod.mjs gen ' + poem + '` 生成;不要手改。规格来源:`demand.json` + `specs/kinds.json`。', '',
      '| 优先级 | 任务 | 类型 | 等级 | 状态 | 占位 | 暂不可派发 |', '|---|---|---|---|---|---|---|',
      ...[...tasks].sort((a, b) => a.priority.localeCompare(b.priority) || a.task_id.localeCompare(b.task_id)).map((t) => `| ${t.priority} | [\`${t.task_id}\`](sheets/${t.task_id}.md) ${t.title} | ${t.type} | ${t.level ?? '—'} | ${st.tasks[t.task_id].state} | ${regOf(t.asset_id)?.placeholder?.is_placeholder ? '有' : '—'} | ${t.dispatch_hold ? '是' : ''} |`),
      '', '## 暂不可派发的原因', '', ...Object.entries(demand.holds || {}).map(([k, v]) => `- **${k}**:${v}`), ''];
    writeFileSync(join(dir, 'INDEX.md'), idx.join('\n'));
    warnings.concat(chk.warnings).forEach((w) => console.warn('!', w));
    console.log(`gen ${poem}: ${tasks.length} 个任务单 → tasks/${poem}/{tasks.json,INDEX.md,sheets/}`);
  },
  list(poem) {
    const { tasks } = poemTasks(poem); const st = ensureState(loadState(poem), tasks);
    for (const t of tasks) console.log(`${t.priority} ${t.task_id.padEnd(26)} ${String(t.level ?? '—').padEnd(3)} ${st.tasks[t.task_id].state.padEnd(15)}${t.dispatch_hold ? ' [HOLD]' : ''}`);
  },
  state(poem, id, to) {
    if (!to) die('usage: state <poem> <task> <to_state> --by X [--assignee Y] [--note ...]', 2);
    const { tasks } = poemTasks(poem); const t = findTask(tasks, id); const st = ensureState(loadState(poem), tasks);
    if (to === 'DISPATCHED' && t.dispatch_hold && !has('override-hold')) die(`任务 ${id} 暂不可派发:${t.dispatch_hold}\n(解除后再派发;确需强行派发加 --override-hold 并写 --note 理由)`);
    if (to === 'HUMAN_ACCEPTED') { // 验收人不能是交付人
      const dj = join(inboxDir(id), 'delivery.json'); const author = existsSync(dj) ? readJson(dj).author : null;
      if (author && flag('by') === author) die('验收人不能与交付人相同');
    }
    const rec = transition(st, id, to, { by: flag('by'), note: flag('note'), assignee: flag('assignee') });
    saveState(poem, st); console.log(`${id}: → ${rec.state}`);
  },
  'init-delivery'(poem, id) {
    const { tasks } = poemTasks(poem); const t = findTask(tasks, id); const dir = inboxDir(id); mkdirSync(dir, { recursive: true });
    const p = join(dir, 'delivery.json'); if (existsSync(p)) die(`${p} 已存在`);
    writeFileSync(p, JSON.stringify({ schema_version: '1.0', task_id: id, delivered_at: new Date().toISOString(), author: '',
      rights: { origin: '', license: '', workflow: '', human_fix: false, evidence: [] }, notes: '' }, null, 2) + '\n');
    console.log(`已建 ${p}。请填写 author 和 rights(必填项:${t.rights_requirements.must_provide.join('、')}),把交付物放进 inbox/${id}/`);
  },
  check(poem, id) {
    const { tasks } = poemTasks(poem); const t = findTask(tasks, id); const st = ensureState(loadState(poem), tasks);
    const r = fullCheck(t, inboxDir(id));
    const ok = r.errors.length === 0;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${id}: ${r.files.length} 个文件, ${r.errors.length} 错误, ${r.warnings.length} 警告`);
    r.errors.forEach((e) => console.log('  ✗', e)); r.warnings.forEach((w) => console.log('  !', w));
    if (!has('dry')) {
      const rec = st.tasks[id];
      if (rec.state === 'DISPATCHED') transition(st, id, 'DELIVERED', { by: 'check', note: '检测到交付' });
      if (st.tasks[id].state !== 'DELIVERED') { saveState(poem, st); die(`当前状态 ${st.tasks[id].state},只有 DISPATCHED/DELIVERED 能机检(先派发)。`); }
      if (ok) transition(st, id, 'AUTO_PASSED', { by: 'check' }); else transition(st, id, 'REJECTED', { by: 'check', note: r.errors.slice(0, 5).join(' | ') });
      saveState(poem, st); console.log(`  状态 → ${st.tasks[id].state}`);
    }
    process.exitCode = ok ? 0 : 1;
  },
  publish(poem, id) {
    const { tasks, bundle } = poemTasks(poem); const t = findTask(tasks, id); const st = ensureState(loadState(poem), tasks);
    if (st.tasks[id].state !== 'HUMAN_ACCEPTED') die(`${id} 状态是 ${st.tasks[id].state},只有 HUMAN_ACCEPTED 才能发布`);
    const dir = inboxDir(id); const r = fullCheck(t, dir);
    if (r.errors.length) die('入库前复检未通过:\n' + r.errors.map((e) => '  ✗ ' + e).join('\n'));
    if (r.delivery.placeholder) die('交付声明为占位素材,不能走正式发布(用 placeholder 命令登记)');
    ingest(t, dir, r, { placeholder: false, scriptId: bundle?.script_id });
    transition(st, id, 'PUBLISHED', { by: 'publish' }); saveState(poem, st);
    console.log(`published ${id} → published/${t.registry ? 'assets' : 'resources'}/${id}/`);
  },
  placeholder(poem, ...ids) {
    const { tasks, bundle } = poemTasks(poem); const st = ensureState(loadState(poem), tasks);
    const targets = (ids.length ? ids.map((i) => findTask(tasks, i)) : tasks).filter((t) => existsSync(join(inboxDir(t.task_id), 'delivery.json')));
    targets.sort((a, b) => levelRank(a.level ?? 'L0') - levelRank(b.level ?? 'L0')); // 低层先入库,fallback 才存在
    let n = 0, bad = 0;
    for (const t of targets) {
      const dir = inboxDir(t.task_id); const r = fullCheck(t, dir);
      if (!r.delivery?.placeholder) continue;
      if (r.errors.length) { bad++; console.log(`FAIL ${t.task_id}`); r.errors.forEach((e) => console.log('  ✗', e)); continue; }
      ingest(t, dir, r, { placeholder: true, scriptId: bundle?.script_id });
      st.tasks[t.task_id].placeholder = { registered_at: new Date().toISOString() }; n++;
      console.log(`ok   placeholder ${t.task_id} (${t.level ?? 'resource'})`);
    }
    saveState(poem, st); console.log(`登记占位 ${n} 个,失败 ${bad} 个`); process.exitCode = bad ? 1 : 0;
  },
  /** 把 demand.bundle 指向的剧本与登记素材合成候选 bundle(只写 /tmp),交给 A 的编译器只读检查(--check-only)与 12 规则校验。 */
  'compile-check'(poem, factsArg) {
    const { demand } = poemTasks(poem);
    const scriptSrc = resolve(PRODUCTION_ROOT, demand.bundle);
    const assetsFile = join(PUBLISHED, 'bundles', `${poem}.assets.json`);
    if (!existsSync(assetsFile)) die(`先运行 bundle-refs ${poem}`);
    const script = readJson(scriptSrc), refs = readJson(assetsFile);
    const out = join('/tmp', `qj-${poem}`); mkdirSync(out, { recursive: true });
    const cand = join(out, 'candidate.bundle.json');
    writeFileSync(cand, JSON.stringify({ ...script, assets: refs.assets }, null, 2) + '\n');
    const compiler = resolve(PRODUCTION_ROOT, '../../content-agent/pipeline/tools/scene-compiler/compile.mjs');
    const validator = resolve(PRODUCTION_ROOT, '../../content-agent/pipeline/tools/scene-validator/validate.mjs');
    const facts = factsArg ? resolve(factsArg) : resolve(PRODUCTION_ROOT, demand.facts || `tasks/${poem}/facts.mock.json`);
    const run1 = spawnSync(process.execPath, [compiler, '--script', cand, '--facts', facts, '--check-only'], { encoding: 'utf8' });
    const run2 = spawnSync(process.execPath, [validator, cand, '--facts', facts], { encoding: 'utf8' });
    console.log(`candidate: ${cand}\nfacts:     ${facts}`);
    console.log(`--- compile --check-only (exit ${run1.status}) ---\n${run1.stdout || run1.stderr}`);
    console.log(`--- validate (exit ${run2.status}) ---\n${run2.stdout || run2.stderr}`);
    process.exitCode = run1.status === 0 && run2.status === 0 ? 0 : 1;
  },
  'registry-check'() {
    const reg = loadRegistry(); const r = checkRegistry(reg);
    r.errors.forEach((e) => console.log('✗', e)); r.warnings.forEach((w) => console.log('!', w));
    console.log(`${r.errors.length ? 'FAIL' : 'ok'}  registry: ${reg.assets.length} 项, ${r.errors.length} 错误, ${r.warnings.length} 警告`);
    process.exitCode = r.errors.length ? 1 : 0;
  },
  'bundle-refs'(poem) {
    const { tasks, bundle } = poemTasks(poem); const reg = loadRegistry(); const out = { schema_version: '1.0', poem, script_id: bundle?.script_id ?? null, generated_at: new Date().toISOString(), uri_root: 'published/', assets: {}, usage: {}, missing: [], placeholders: [] };
    for (const t of tasks.filter((x) => x.registry)) {
      const a = reg.assets.find((x) => x.asset_id === t.asset_id);
      if (!a) { out.missing.push(t.asset_id); continue; }
      const files = {}; const layers = [];
      for (const f of a.files) { const fmt = f.format || f.path.split('.').pop(); if (f.role === 'layer') layers.push(f.path); else if (f.role === 'entry') files[fmt] = f.path; else if (f.role !== 'script') files[f.role] = f.path; }
      if (layers.length) files.layers = layers;
      const rights = { origin: a.rights.origin, license: a.rights.license, ...(a.rights.workflow ? { workflow: a.rights.workflow } : {}), ...(a.rights.human_fix !== undefined ? { human_fix: a.rights.human_fix } : {}) };
      out.assets[a.asset_id] = { kind: a.kind, level: a.level, hash: a.hash, files, fallback: a.level === 'L0' ? ['L0-text'] : [a.fallback_asset_id], rights, meaning: a.meaning, ...(a.render ? { render: a.render } : {}), ...(a.placeholder.is_placeholder ? { placeholder: true } : {}) };
      out.usage[a.asset_id] = t.usage.bundle_refs;
      if (a.placeholder.is_placeholder) out.placeholders.push(a.asset_id);
    }
    if (flag('channel') === 'production' && out.placeholders.length)
      die(`生产渠道拒绝占位素材(not_for_release):${out.placeholders.join('、')}\n(开发/内测渠道不加 --channel production)`);
    if (flag('channel') === 'production' && out.missing.length)
      die(`生产渠道要求所有登记素材齐全,缺:${out.missing.join('、')}`);
    mkdirSync(join(PUBLISHED, 'bundles'), { recursive: true });
    writeFileSync(join(PUBLISHED, 'bundles', `${poem}.assets.json`), JSON.stringify(out, null, 2) + '\n');
    console.log(`bundle-refs ${poem}: ${Object.keys(out.assets).length} 项已登记, ${out.missing.length} 项尚无素材, ${out.placeholders.length} 项占位 → published/bundles/${poem}.assets.json`);
  },
  report(...poems) {
    const names = poems.length ? poems : listPoems(); const L = ['# 素材生产进度', '', `生成时间:${new Date().toISOString()}(由 \`node tools/prod.mjs report\` 生成,勿手改)`, ''];
    const reg = loadRegistry(); const rc = checkRegistry(reg);
    for (const poem of names) {
      const { tasks, demand } = poemTasks(poem); const st = ensureState(loadState(poem), tasks);
      const by = (f) => tasks.reduce((m, t) => ((m[f(t)] = (m[f(t)] || 0) + 1), m), {});
      L.push(`## ${demand.title}`, '', `共 ${tasks.length} 个任务。`, '', '状态:' + Object.entries(by((t) => st.tasks[t.task_id].state)).map(([k, v]) => `${k} ${v}`).join(' · '), '');
      const regOf = (id) => reg.assets.find((a) => a.asset_id === id);
      const phs = tasks.filter((t) => regOf(t.asset_id)?.placeholder?.is_placeholder), real = tasks.filter((t) => regOf(t.asset_id) && !regOf(t.asset_id).placeholder.is_placeholder);
      const none = tasks.filter((t) => t.registry && !regOf(t.asset_id));
      L.push(`- 已有正式素材:**${real.length}**`, `- 仅有占位(不可上线):**${phs.length}**`, `- 既无正式也无占位(前端走降级):**${none.length}**`, `- 暂不可派发(依据未定):**${tasks.filter((t) => t.dispatch_hold).length}**`, '');
      L.push('| 优先级 | 任务 | 等级 | 状态 | 素材现状 | 暂不可派发 |', '|---|---|---|---|---|---|');
      for (const t of [...tasks].sort((a, b) => a.priority.localeCompare(b.priority) || a.task_id.localeCompare(b.task_id))) {
        const a = regOf(t.asset_id);
        L.push(`| ${t.priority} | \`${t.task_id}\` ${t.title} | ${t.level ?? '—'} | ${st.tasks[t.task_id].state} | ${!t.registry ? (existsSync(join(PUBLISHED, 'resources', t.asset_id)) ? '已入库' : '无') : a ? (a.placeholder.is_placeholder ? '占位' : '正式') : '无'} | ${t.dispatch_hold ? '⚠ ' + Object.entries(demand.holds).find(([, v]) => v === t.dispatch_hold)?.[0] : ''} |`);
      }
      L.push('', '### 需要用户先解决的卡点', '', ...Object.entries(demand.holds || {}).map(([k, v]) => { const n = tasks.filter((t) => t.dispatch_hold === v); return `- **${k}**(挡住 ${n.length} 个任务:${n.map((t) => t.task_id).join('、') || '—'}):${v}`; }), '');
    }
    L.push('## 登记簿', '', `${reg.assets.length} 项;登记检查:${rc.errors.length ? '**有错误**' : '通过'}。`, ...rc.errors.map((e) => `- ✗ ${e}`));
    mkdirSync(join(PRODUCTION_ROOT, 'reports'), { recursive: true });
    writeFileSync(join(PRODUCTION_ROOT, 'reports', 'progress.md'), L.join('\n') + '\n'); console.log(L.join('\n'));
  },
};

if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname)) {
  const fn = commands[cmd]; if (!fn) die(`usage: prod.mjs <${Object.keys(commands).join('|')}> ...`, 2);
  try { fn(...pos); } catch (e) { die(`错误:${e.message}`); }
}
