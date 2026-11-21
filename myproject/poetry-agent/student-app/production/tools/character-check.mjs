#!/usr/bin/env node
// 角色清单机检:schema + 交叉引用 + 文件存在/画布/预算。零依赖。
// 用法: node character-check.mjs <manifest.json>...   退出码 0=通过 1=有问题 2=用法错误
import { readFileSync, existsSync, statSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { validate } from './lib/jsonschema.mjs';
import { schema, readJson } from './lib/registry.mjs';

export function checkCharacter(manifestPath) {
  const errors = [], warnings = [];
  const dir = dirname(resolve(manifestPath));
  const m = readJson(manifestPath);
  errors.push(...validate(schema('character.schema.json'), m));
  if (errors.length) return { errors, warnings, manifest: m };
  const E = (s) => errors.push(s);

  const layers = new Map((m.layers || []).map((l) => [l.id, l]));
  if (m.renderer === 'svg-layers') {
    if (!m.layers?.length) E('renderer=svg-layers 必须有 layers');
    if ((m.layers || []).length !== layers.size) E('图层 id 重复');
    for (const l of m.layers || []) {
      if (l.type === 'group' && l.file) E(`${l.id}: group 不应带 file`);
      if (l.type !== 'group' && !l.file) E(`${l.id}: ${l.type} 图层缺 file`);
      if (l.parent && !layers.has(l.parent)) E(`${l.id}: parent ${l.parent} 不存在`);
      // 无环
      let cur = l, n = 0;
      while (cur?.parent && n++ < 20) cur = layers.get(cur.parent);
      if (n >= 20) E(`${l.id}: parent 链成环`);
      if (l.file) {
        const p = join(dir, l.file);
        if (!existsSync(p)) E(`${l.id}: 文件不存在 ${l.file}`);
        else if (l.file.endsWith('.svg')) {
          const t = readFileSync(p, 'utf8');
          const vb = t.match(/viewBox="([^"]+)"/)?.[1];
          if (vb !== `0 0 ${m.canvas.width} ${m.canvas.height}`) E(`${l.id}: viewBox "${vb}" != 画布 0 0 ${m.canvas.width} ${m.canvas.height}`);
          if (/<script|on\w+=|href="https?:|xlink:href="https?:/i.test(t)) E(`${l.id}: SVG 含脚本或外部引用`);
        }
      }
    }
  } else {
    if (!m.entry) E(`renderer=${m.renderer} 必须有 entry`);
    else if (!existsSync(join(dir, m.entry))) E(`entry 不存在 ${m.entry}`);
  }

  // 锚点在画布内
  for (const [k, p] of Object.entries(m.anchors)) if (p.x < 0 || p.y < 0 || p.x > m.canvas.width || p.y > m.canvas.height) E(`锚点 ${k} 在画布外`);

  // 状态
  if (!m.states.idle) E('必须有 idle 状态');
  if (!m.states[m.default_state]) E(`default_state ${m.default_state} 不存在`);
  for (const [name, s] of Object.entries(m.states)) {
    for (const k of ['then', 'fallback_state']) if (s[k] && !m.states[s[k]]) E(`${name}.${k} -> ${s[k]} 不存在`);
    if (!s.loop && !s.then) warnings.push(`${name}: 非循环状态没有 then,播完停在最后一帧`);
    if (m.renderer === 'svg-layers') {
      for (const id of [...(s.show || []), ...(s.hide || [])]) if (!layers.has(id)) E(`${name}: show/hide 引用了不存在的图层 ${id}`);
      for (const t of s.tracks || []) {
        if (!layers.has(t.layer)) E(`${name}: 轨道引用了不存在的图层 ${t.layer}`);
        let prev = -1;
        for (const [ms] of t.keyframes) { if (ms < prev) E(`${name}/${t.layer}.${t.prop}: 关键帧时间必须递增`); prev = ms; }
        if (s.duration_ms && t.keyframes.at(-1)[0] > s.duration_ms) E(`${name}/${t.layer}.${t.prop}: 关键帧超过 duration_ms`);
        if (s.loop && s.duration_ms) {
          const a = t.keyframes[0][1], b = t.keyframes.at(-1)[1];
          if (a !== b) warnings.push(`${name}/${t.layer}.${t.prop}: 循环状态首尾值不同(${a} vs ${b}),循环处会跳变`);
        }
      }
    }
    if (m.renderer === 'frames') {
      if (!s.frames?.length) E(`${name}: frames 渲染器需要 frames`);
      for (const f of s.frames || []) if (!existsSync(join(dir, f.file))) E(`${name}: 帧文件不存在 ${f.file}`);
    }
    // fallback 链到 idle,无环
    if (name !== 'idle') {
      let cur = name, steps = 0;
      while (cur && cur !== 'idle' && steps++ < 8) cur = m.states[cur]?.fallback_state;
      if (cur !== 'idle') E(`${name}: fallback_state 链没有到达 idle`);
    }
  }
  if (!m.states[m.degrade.reduced_motion_state]) E(`degrade.reduced_motion_state ${m.degrade.reduced_motion_state} 不存在`);
  if (!existsSync(join(dir, m.degrade.still.file))) E(`degrade.still 文件不存在 ${m.degrade.still.file}`);

  // mouth
  if (m.mouth_mode === 'amplitude') {
    if (!m.mouth) E('mouth_mode=amplitude 必须有 mouth 配置');
    else if (m.renderer === 'svg-layers' && !layers.has(m.mouth.layer)) E(`mouth.layer ${m.mouth.layer} 不存在`);
  }
  if (m.mouth_mode === 'none' && m.mouth) warnings.push('mouth_mode=none 但写了 mouth 配置,将被忽略');

  // ambient
  const bl = m.ambient?.blink;
  if (bl && m.renderer === 'svg-layers') {
    for (const k of ['open_layer', 'closed_layer']) if (!layers.has(bl[k])) E(`ambient.blink.${k} ${bl[k]} 不存在`);
    if (bl.interval_ms[0] > bl.interval_ms[1]) E('ambient.blink.interval_ms 应为 [最小, 最大]');
    for (const s of bl.suppress_in || []) if (!m.states[s]) E(`ambient.blink.suppress_in 状态 ${s} 不存在`);
  }

  // 占位、预算
  if (m.placeholder.is_placeholder && !m.placeholder.not_for_release) E('占位角色必须 not_for_release=true');
  if (!m.placeholder.is_placeholder && m.rights.origin.includes('代码生成')) E('代码生成的角色必须标 placeholder.is_placeholder=true');
  const used = new Set([m.degrade.still.file, m.entry, ...(m.layers || []).map((l) => l.file), ...Object.values(m.states).flatMap((s) => (s.frames || []).map((f) => f.file))].filter(Boolean));
  let total = statSync(manifestPath).size;
  for (const f of used) { const p = join(dir, f); if (existsSync(p)) total += statSync(p).size; }
  if (total > m.budget.max_bytes) E(`总字节 ${total} 超过 budget.max_bytes ${m.budget.max_bytes}`);
  return { errors, warnings, manifest: m, totalBytes: total, files: [...used] };
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname)) {
  const paths = process.argv.slice(2);
  if (!paths.length) { console.error('usage: node character-check.mjs <manifest.json>...'); process.exit(2); }
  let bad = 0;
  for (const p of paths) {
    const r = checkCharacter(p);
    const tag = r.errors.length ? 'FAIL' : 'ok  ';
    console.log(`${tag} ${p}${r.totalBytes ? `  (${r.totalBytes} bytes)` : ''}`);
    r.errors.forEach((e) => console.log(`   ✗ ${e}`));
    r.warnings.forEach((w) => console.log(`   ! ${w}`));
    if (r.errors.length) bad++;
  }
  process.exit(bad ? 1 : 0);
}
