// 任务库:由 demand.json + kinds.json + bundle 推导任务单;状态机;人读 Markdown。
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { PRODUCTION_ROOT, LEVELS, levelRank, readJson, schema } from './registry.mjs';
import { validate } from './jsonschema.mjs';

export const taskDir = (poem) => join(PRODUCTION_ROOT, 'tasks', poem);
export const getPath = (obj, path) => path.split(/[.\[\]]+/).filter(Boolean).reduce((o, k) => (o == null ? undefined : o[k]), obj);
const sha = (s) => createHash('sha256').update(s, 'utf8').digest('hex');
const FIVE = ['read', 'arrive', 'meet', 'return', 'recite'];

const ORIGINS = {
  illustration: ['自绘', '外包绘制', 'AI 生成(须写明模型与版本,且经人工修复)', '自生成占位'],
  map: ['自绘', '外包绘制', '自生成占位'],
  character: ['自绘', '外包制作', 'AI 辅助(须写明且经人工修复)', '自生成占位'],
  audio: ['真人录音(须附朗读人授权)', '授权合成音(须写明模型、版本与授权范围)', '自生成占位'],
  voice: ['授权合成音(须写明模型、版本与授权范围)', '真人音色(须附书面授权)', '自生成占位'],
  subtitle: ['由底座/剧本文本派生', '自生成占位'],
  font: ['开源字体(须附许可原文)', '购买授权(须附授权书)'],
};
const FORBIDDEN_ORIGIN = ['来源不明', '网络下载', '网图', '盗版'];

export function loadContext(poem) {
  const demand = readJson(join(taskDir(poem), 'demand.json'));
  const kinds = readJson(join(PRODUCTION_ROOT, 'specs', 'kinds.json'));
  const bundle = demand.bundle && existsSync(resolve(PRODUCTION_ROOT, demand.bundle)) ? readJson(resolve(PRODUCTION_ROOT, demand.bundle)) : null;
  return { demand, kinds, bundle };
}

const constraintText = (c = {}) => Object.entries(c).map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`).join(', ');

/** 列出所有有 demand.json 的诗(tasks/ 下的目录名)。 */
export function listPoems() {
  const root = join(PRODUCTION_ROOT, 'tasks');
  return existsSync(root) ? readdirSync(root, { withFileTypes: true }).filter((e) => e.isDirectory() && existsSync(join(root, e.name, 'demand.json'))).map((e) => e.name).sort() : [];
}

/** 把类型模板里的 {name} 换成本诗的 vars(缺省取 kinds.json 的 template_defaults)。未知占位符原样保留并产生警告。 */
export function fill(str, vars, defaults, warn) {
  return str.replace(/\{(\w+)\}/g, (m, k) => { const v = vars?.[k] ?? defaults?.[k]; if (v === undefined) { warn?.(`模板变量 {${k}} 没有值`); return m; } return v; });
}

/** 其他诗的任务单里已经占用的 id(跨诗冲突检查:inbox/ 与 published/assets/ 是按 id 平铺的全局命名空间)。 */
export function takenElsewhere(poem) {
  const taken = new Map();
  for (const other of listPoems().filter((p) => p !== poem)) {
    const f = join(taskDir(other), 'tasks.json'); if (!existsSync(f)) continue;
    for (const t of readJson(f).tasks) taken.set(t.task_id, other);
  }
  return taken;
}

export function buildTasks(poem) {
  const { demand, kinds, bundle } = loadContext(poem);
  const warnings = [];
  const tasks = demand.tasks.map((d) => {
    const k = kinds.types[d.type];
    if (!k) throw new Error(`${d.id}: 未知任务类型 ${d.type}`);
    let script = null;
    if (d.text_from) {
      const t = bundle ? getPath(bundle, d.text_from) : undefined;
      if (typeof t === 'string') script = t; else warnings.push(`${d.id}: text_from ${d.text_from} 在 bundle 中取不到文本`);
    } else if (d.script_text) script = d.script_text;
    const hold = d.hold ? demand.holds?.[d.hold] : undefined;
    if (d.hold && !hold) warnings.push(`${d.id}: hold「${d.hold}」未在 demand.holds 中定义`);
    const sub = (s) => fill(s, demand.vars, kinds.template_defaults, (w) => warnings.push(`${d.id}: ${w}`));
    // 按任务覆盖约束:demand 任务里的 constraints.<role> 浅合并进同角色交付物(例:短诗放宽诵读时长下限)
    const deliverables = k.deliverables.map((x) => (d.constraints?.[x.role] ? { ...x, constraints: { ...x.constraints, ...d.constraints[x.role] } } : x));
    for (const role of Object.keys(d.constraints || {})) if (!k.deliverables.some((x) => x.role === role)) warnings.push(`${d.id}: constraints.${role} 没有对应的交付物角色`);
    const auto = [`交付目录 inbox/${d.id}/ 含 delivery.json(来源、授权、交付人)`];
    for (const x of deliverables) auto.push(`${x.role}:${x.filename}(${x.formats.join('/')})${x.required ? ' 必需' : ' 可选'}${x.min_count ? `,至少 ${x.min_count} 个` : ''}${x.max_count ? `,至多 ${x.max_count} 个` : ''}${x.constraints ? ';' + constraintText(x.constraints) : ''}`);
    if (script) auto.push('文字类交付物(字幕/文字卡/脚本)与任务单 brief.script_text 逐字一致(忽略空白)');
    const human = [...k.human_checklist.map(sub), '版权:delivery.json 的来源与授权真实、完整、覆盖商用'];
    if (d.depiction === 'DRAMATIZATION') human.push('已确认界面会带『演绎』标识,素材本身不冒充史料');
    const task = {
      task_id: d.id, poem, type: d.type, title: d.title, asset_id: d.id,
      kind: k.kind, level: k.level, render: k.render, registry: k.registry, priority: d.priority,
      usage: { steps: d.steps, ...(d.layers ? { layers: d.layers } : {}), ...(d.line_seqs ? { line_seqs: d.line_seqs, lines_text: d.line_seqs.map((n) => demand.poem_lines.find((l) => l.seq === n)?.text).filter(Boolean) } : {}),
               bundle_refs: d.bundle_refs || [], purpose: d.purpose },
      deliverables,
      rights_requirements: {
        must_provide: ['origin', 'license', ...(['audio', 'voice'].includes(k.kind) ? ['evidence'] : []), ...(k.kind === 'font' ? ['evidence'] : [])],
        allowed_origins: ORIGINS[k.kind || 'font'] || [],
        forbidden: FORBIDDEN_ORIGIN,
        evidence: ['audio', 'voice'].includes(k.kind) ? '真人:朗读人书面授权/同意书编号;合成音:服务条款或授权书中覆盖商用的条款' : k.kind === 'font' ? '字体许可原文(必须覆盖商用+网页嵌入+子集化)' : '外包:合同编号;AI 生成:工作流 JSON@hash;自绘:作者声明',
      },
      acceptance: { auto, human },
      fallback: { fallback_asset_id: d.fallback ?? null, note: k.fallback_type ? `降级目标类型:${k.fallback_type}` : '降级终点或不参与降级' },
      brief: {
        creative_notes: d.creative, style: k.style.map(sub), grounding: d.grounding,
        forbidden_elements: [...(demand.global_forbidden || []), ...(d.forbidden || [])],
        depiction: d.depiction, references: [],
        ...(script ? { script_text: script, script_text_sha256: sha(script) } : {}),
      },
      placeholder_plan: d.placeholder || { strategy: 'none' },
      source: { demand: `tasks/${poem}/demand.json`, bundle: demand.bundle, ...(d.text_from ? { text_from: d.text_from } : {}) },
      ...(hold ? { dispatch_hold: hold } : {}),
      ...(d.companion_of ? { companion_of: d.companion_of } : {}),
      ...(d.depends_on ? { depends_on: d.depends_on } : {}),
    };
    return task;
  });
  return { tasks, warnings, demand, bundle };
}

/** 任务单自身的完整性检查:schema、id 唯一、降级链严格降层且到 L0、依赖存在、bundle 覆盖。 */
export function checkTasks(tasks, bundle) {
  const errors = [], warnings = [];
  const s = schema('task.schema.json');
  const byId = new Map();
  for (const t of tasks) {
    errors.push(...validate(s, t).map((e) => `${t.task_id} ${e}`));
    if (byId.has(t.task_id)) errors.push(`${t.task_id}: 重复`); byId.set(t.task_id, t);
  }
  for (const t of tasks) {
    if (!t.registry) continue;
    const fb = t.fallback.fallback_asset_id;
    if (t.level === 'L0') { if (fb) errors.push(`${t.task_id}: L0 不得有 fallback`); }
    else if (!fb) errors.push(`${t.task_id}: 非 L0 必须有 fallback`);
    else {
      const low = byId.get(fb);
      if (!low) errors.push(`${t.task_id}: fallback ${fb} 没有对应任务单`);
      else if (!low.registry) errors.push(`${t.task_id}: fallback ${fb} 不是登记素材`);
      else if (levelRank(low.level) >= levelRank(t.level)) errors.push(`${t.task_id}: fallback 必须严格降层 ${t.level} -> ${low.level}(Java 规则)`);
    }
    for (const d of t.depends_on || []) if (!byId.has(d)) errors.push(`${t.task_id}: depends_on ${d} 不存在`);
    if (t.companion_of && !byId.has(t.companion_of)) errors.push(`${t.task_id}: companion_of ${t.companion_of} 不存在`);
    if (t.usage.purpose.trim().length < 8) errors.push(`${t.task_id}: purpose < 8 字`);
  }
  if (bundle) {
    const ids = new Set(tasks.map((t) => t.asset_id));
    for (const id of Object.keys(bundle.assets || {})) if (!ids.has(id)) warnings.push(`bundle 声明了素材 ${id},但没有对应任务单`);
    // 样例 bundle 自身的降层问题(给 B/A 的信息,不是本目录的错误)
    for (const [id, a] of Object.entries(bundle.assets || {})) {
      const next = bundle.assets[a.fallback?.[0]];
      if (next && levelRank(next.level) >= levelRank(a.level)) warnings.push(`样例 bundle: ${id}(${a.level}) 的 fallback ${a.fallback[0]}(${next.level}) 不是严格降层,Java createAsset 会拒绝`);
    }
  }
  return { errors, warnings };
}

/* ---------------- 状态 ---------------- */
export const loadMachine = () => readJson(join(PRODUCTION_ROOT, 'specs', 'state-machine.json'));
const statePath = (poem) => join(taskDir(poem), 'state.json');
export function loadState(poem) { return existsSync(statePath(poem)) ? readJson(statePath(poem)) : { poem, tasks: {} }; }
export function saveState(poem, st) { writeFileSync(statePath(poem), JSON.stringify(st, null, 2) + '\n'); }
export function ensureState(st, tasks) {
  for (const t of tasks) st.tasks[t.task_id] ||= { state: 'TODO', assignee: null, history: [] };
  return st;
}
export function transition(st, taskId, to, { by, note, assignee } = {}) {
  const rec = st.tasks[taskId]; if (!rec) throw new Error(`状态里没有任务 ${taskId}(先运行 gen)`);
  const rule = loadMachine().transitions.find((x) => x.from === rec.state && x.to === to);
  if (!rule) throw new Error(`不允许 ${rec.state} -> ${to}`);
  if (to === 'DISPATCHED' && !(assignee || rec.assignee)) throw new Error('派发必须写明 --assignee');
  if (['HUMAN_ACCEPTED'].includes(to) && !by) throw new Error('人工验收必须写明 --by 验收人');
  if (to === 'REJECTED' && !note) throw new Error('退回必须写明原因 --note');
  if (assignee) rec.assignee = assignee;
  rec.history.push({ at: new Date().toISOString(), from: rec.state, to, by: by || null, note: note || null });
  rec.state = to;
  return rec;
}

/* ---------------- Markdown ---------------- */
export function renderMarkdown(t, rec, regEntry) {
  const L = [];
  L.push(`# 任务单:${t.title}`, '');
  L.push(`| 项 | 值 |`, `|---|---|`);
  L.push(`| 任务/素材 id | \`${t.task_id}\` |`, `| 诗 | ${t.poem} |`, `| 类型 | ${t.type} |`);
  L.push(`| 登记 kind / level | ${t.registry ? `${t.kind} / ${t.level}(render: ${t.render})` : '不进 poetry_asset(资源文件)'} |`, `| 优先级 | ${t.priority} |`);
  L.push(`| 当前状态 | **${rec?.state || 'TODO'}**${rec?.assignee ? `(领取:${rec.assignee})` : ''} |`);
  L.push(`| 占位素材 | ${regEntry?.placeholder?.is_placeholder ? '已有占位(不可上线),等待正式交付替换' : '无'} |`);
  if (t.dispatch_hold) L.push(`| ⚠ 暂不可派发 | ${t.dispatch_hold} |`);
  if (t.companion_of) L.push(`| 降级伴生于 | \`${t.companion_of}\` |`);
  if (t.depends_on?.length) L.push(`| 依赖 | ${t.depends_on.map((x) => `\`${x}\``).join('、')} |`);
  L.push('', '## 用途(= 登记 meaning)', '', t.usage.purpose, '');
  L.push(`- 用于步骤:${t.usage.steps.join('、')}${t.usage.layers ? `;层:${t.usage.layers.join('、')}` : ''}`);
  if (t.usage.line_seqs) L.push(`- 对应诗句:${t.usage.line_seqs.map((n, i) => `第${n}句「${t.usage.lines_text?.[i] ?? ''}」`).join('、')}`);
  if (t.usage.bundle_refs.length) L.push(`- bundle 引用位置:${t.usage.bundle_refs.map((x) => `\`${x}\``).join('、')}`);
  L.push('', '## 交付物与规格', '', '| 角色 | 文件名 | 格式 | 必需 | 约束 |', '|---|---|---|---|---|');
  for (const d of t.deliverables) L.push(`| ${d.role} | \`${d.filename}\` | ${d.formats.join('/')} | ${d.required ? '是' : '否'} | ${constraintText(d.constraints) || '—'}${d.note ? `<br>${d.note}` : ''} |`);
  L.push('', '交付方式:把文件放进 `inbox/' + t.task_id + '/`,并附 `delivery.json`(来源、授权、交付人;格式见 `contracts/delivery.schema.json`)。然后运行 `node tools/prod.mjs check ' + t.poem + ' ' + t.task_id + '`。', '');
  L.push('## 版权与来源要求', '', `- delivery.json 必须填写:${t.rights_requirements.must_provide.join('、')}`, `- 可接受的来源:${t.rights_requirements.allowed_origins.join(';')}`, `- 不接受:${t.rights_requirements.forbidden.join('、')}`, `- 证明材料:${t.rights_requirements.evidence}`, '');
  L.push('## 验收标准', '', '### 机检(脚本自动执行)', '', ...t.acceptance.auto.map((x) => `- [ ] ${x}`), '', '### 人工验收', '', ...t.acceptance.human.map((x) => `- [ ] ${x}`), '');
  L.push('## 降级关系', '', t.fallback.fallback_asset_id ? `失效时降到 \`${t.fallback.fallback_asset_id}\`(必须严格低一级,最终到 L0 文字)。` : '这是降级终点(L0 文字)或不参与降级。', '');
  L.push('## 创作说明', '', t.brief.creative_notes, '');
  L.push(`- 性质:**${{ FACT: '史实', INTERPRETATION: '解释', DRAMATIZATION: '演绎(界面需带「演绎」标识,不得当作史实)' }[t.brief.depiction]}**`);
  L.push(`- 依据:${t.brief.grounding}`);
  if (t.brief.style?.length) L.push('- 风格/技术约束:', ...t.brief.style.map((x) => `  - ${x}`));
  L.push('- 禁止出现:', ...t.brief.forbidden_elements.map((x) => `  - ${x}`));
  if (t.brief.script_text) L.push('', '### 逐字脚本(不得增删)', '', '> ' + t.brief.script_text);
  L.push('', '## 占位与状态机', '', `- 占位策略:${t.placeholder_plan.strategy}${t.placeholder_plan.note ? `(${t.placeholder_plan.note})` : ''}`, '- 状态:TODO → 已派发(DISPATCHED) → 已交付(DELIVERED) → 机检通过(AUTO_PASSED) → 人工验收(HUMAN_ACCEPTED) → 已发布(PUBLISHED);任一环节不通过 → 退回(REJECTED)→ 重新派发。');
  if (rec?.history?.length) { L.push('', '## 历史', '', ...rec.history.map((h) => `- ${h.at} ${h.from} → ${h.to}${h.by ? ` by ${h.by}` : ''}${h.note ? `:${h.note}` : ''}`)); }
  return L.join('\n') + '\n';
}
