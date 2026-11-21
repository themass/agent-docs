// 机检引擎:按 deliverables[].constraints 检查交付文件。零网络。
// 图片尺寸/alpha 自己解析文件头(PNG/WebP/JPEG/SVG);WAV 自己解析;m4a/mp3 需要 ffprobe,没有就给 warning 而不是静默通过。
import { readFileSync, statSync, readdirSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, extname, basename } from 'node:path';
import { validate } from './jsonschema.mjs';
import { schema } from './registry.mjs';

/* ---------- 文件头解析 ---------- */
export function pngInfo(buf) {
  if (buf.length < 33 || buf.readUInt32BE(0) !== 0x89504e47) return null;
  const colorType = buf[25];
  let hasTrns = false;
  for (let p = 8; p + 8 <= buf.length;) { const len = buf.readUInt32BE(p), type = buf.toString('latin1', p + 4, p + 8); if (type === 'tRNS') hasTrns = true; if (type === 'IDAT') break; p += 12 + len; }
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20), alpha: colorType === 4 || colorType === 6 || hasTrns };
}
export function webpInfo(buf) {
  if (buf.length < 30 || buf.toString('latin1', 0, 4) !== 'RIFF' || buf.toString('latin1', 8, 12) !== 'WEBP') return null;
  const fmt = buf.toString('latin1', 12, 16);
  if (fmt === 'VP8X') return { width: 1 + buf.readUIntLE(24, 3), height: 1 + buf.readUIntLE(27, 3), alpha: !!(buf[20] & 0x10) };
  if (fmt === 'VP8L') { const b = buf.readUInt32LE(21); return { width: 1 + (b & 0x3fff), height: 1 + ((b >> 14) & 0x3fff), alpha: !!((b >> 28) & 1) }; }
  if (fmt === 'VP8 ') return { width: buf.readUInt16LE(26) & 0x3fff, height: buf.readUInt16LE(28) & 0x3fff, alpha: false };
  return null;
}
export function jpegInfo(buf) {
  if (buf[0] !== 0xff || buf[1] !== 0xd8) return null;
  for (let p = 2; p + 9 < buf.length;) { if (buf[p] !== 0xff) { p++; continue; } const m = buf[p + 1];
    if (m >= 0xc0 && m <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(m)) return { width: buf.readUInt16BE(p + 7), height: buf.readUInt16BE(p + 5), alpha: false };
    p += 2 + buf.readUInt16BE(p + 2); }
  return null;
}
export function svgInfo(text) {
  const vb = text.match(/viewBox="\s*([-\d.]+)[\s,]+([-\d.]+)[\s,]+([-\d.]+)[\s,]+([-\d.]+)\s*"/);
  const w = text.match(/<svg[^>]*\swidth="([\d.]+)/), h = text.match(/<svg[^>]*\sheight="([\d.]+)/);
  return { viewBox: vb ? [+vb[1], +vb[2], +vb[3], +vb[4]] : null, width: vb ? +vb[3] : w ? +w[1] : null, height: vb ? +vb[4] : h ? +h[1] : null, alpha: true };
}
export function wavInfo(buf) {
  if (buf.length < 44 || buf.toString('latin1', 0, 4) !== 'RIFF' || buf.toString('latin1', 8, 12) !== 'WAVE') return null;
  let p = 12, fmt = null, dataBytes = null;
  while (p + 8 <= buf.length) { const id = buf.toString('latin1', p, p + 4), len = buf.readUInt32LE(p + 4);
    if (id === 'fmt ') fmt = { channels: buf.readUInt16LE(p + 10), sampleRate: buf.readUInt32LE(p + 12), bits: buf.readUInt16LE(p + 22) };
    if (id === 'data') { dataBytes = Math.min(len, buf.length - p - 8); break; }
    p += 8 + len + (len % 2); }
  if (!fmt || dataBytes == null) return null;
  return { ...fmt, durationMs: Math.round((dataBytes / (fmt.sampleRate * fmt.channels * (fmt.bits / 8))) * 1000) };
}
let ffprobeOk;
export function hasFfprobe() { if (ffprobeOk === undefined) ffprobeOk = spawnSync('ffprobe', ['-version']).status === 0; return ffprobeOk; }
export function ffprobeAudio(path) {
  const r = spawnSync('ffprobe', ['-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate,channels,codec_name:format=duration', '-of', 'json', path], { encoding: 'utf8' });
  if (r.status !== 0) return null;
  try { const j = JSON.parse(r.stdout); const s = j.streams?.[0]; return { sampleRate: +s.sample_rate, channels: s.channels, codec: s.codec_name, durationMs: Math.round(parseFloat(j.format.duration) * 1000) }; } catch { return null; }
}

/** 解析 WebVTT,返回 {cues:[{start,end,text}], errors}。 */
export function parseVtt(text) {
  const errors = [], cues = [];
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/);
  if (!/^WEBVTT/.test(lines[0] || '')) errors.push('第一行必须是 WEBVTT');
  const ts = (s) => { const m = s.match(/^(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})$/); return m ? ((+(m[1] || 0) * 60 + +m[2]) * 60 + +m[3]) * 1000 + +m[4] : null; };
  for (let i = 1; i < lines.length; i++) {
    const m = lines[i].match(/^(\S+)\s+-->\s+(\S+)/);
    if (!m) continue;
    const a = ts(m[1]), b = ts(m[2]);
    if (a == null || b == null) { errors.push(`第 ${i + 1} 行时间格式错误:${lines[i]}`); continue; }
    const body = []; let j = i + 1;
    while (j < lines.length && lines[j].trim() !== '') body.push(lines[j++]);
    cues.push({ start: a, end: b, text: body.join('\n') }); i = j;
  }
  return { cues, errors };
}

const aspectOk = (w, h, spec, tol = 0.02) => { const [a, b] = spec.split(':').map(Number); return Math.abs(w / h - a / b) <= tol * (a / b); };
const dimsOf = (ext, buf) => ext === '.png' ? pngInfo(buf) : ext === '.webp' ? webpInfo(buf) : (ext === '.jpg' || ext === '.jpeg') ? jpegInfo(buf) : ext === '.svg' ? svgInfo(buf.toString('utf8')) : null;

/** 检查单个文件。ctx: {canvas} 供 svg viewBox 对照。返回 {errors, warnings, facts}。 */
export function checkFile(path, constraints = {}, ctx = {}) {
  const errors = [], warnings = [], facts = {};
  const buf = readFileSync(path), ext = extname(path).toLowerCase(), name = basename(path);
  facts.bytes = buf.length;
  if (buf.length === 0) errors.push(`${name}: 文件为空`);
  if (constraints.max_bytes && buf.length > constraints.max_bytes) errors.push(`${name}: ${buf.length} 字节超过上限 ${constraints.max_bytes}`);

  if (['.png', '.webp', '.jpg', '.jpeg', '.svg'].includes(ext)) {
    const d = dimsOf(ext, buf);
    if (!d) { errors.push(`${name}: 不是有效的 ${ext.slice(1)} 文件(文件头不符)`); }
    else {
      Object.assign(facts, { width: d.width, height: d.height, alpha: d.alpha });
      if (constraints.width && d.width !== constraints.width) errors.push(`${name}: 宽 ${d.width} != ${constraints.width}`);
      if (constraints.height && d.height !== constraints.height) errors.push(`${name}: 高 ${d.height} != ${constraints.height}`);
      if (constraints.min_width && d.width < constraints.min_width) errors.push(`${name}: 宽 ${d.width} < ${constraints.min_width}`);
      if (constraints.min_height && d.height < constraints.min_height) errors.push(`${name}: 高 ${d.height} < ${constraints.min_height}`);
      if (constraints.aspect && d.width && d.height && !aspectOk(d.width, d.height, constraints.aspect)) errors.push(`${name}: 宽高比 ${d.width}x${d.height} 不是 ${constraints.aspect}`);
      if (constraints.alpha && !d.alpha) errors.push(`${name}: 需要透明通道`);
    }
    if (ext === '.svg') {
      const t = buf.toString('utf8');
      if (constraints.no_script !== false && /<script|\son\w+\s*=|(?:xlink:)?href\s*=\s*["']\s*(?:https?:|javascript:|data:text\/html)/i.test(t)) errors.push(`${name}: SVG 含脚本、事件属性或外部引用`);
      if (/<foreignObject/i.test(t)) errors.push(`${name}: SVG 含 foreignObject`);
      if (constraints.svg_viewbox_equals_canvas && ctx.canvas) {
        const vb = svgInfo(t).viewBox;
        if (!vb || vb[0] !== 0 || vb[1] !== 0 || vb[2] !== ctx.canvas.width || vb[3] !== ctx.canvas.height) errors.push(`${name}: viewBox ${vb ? vb.join(' ') : '缺失'} != 画布 0 0 ${ctx.canvas.width} ${ctx.canvas.height}`);
      }
    }
  }
  if (['.wav', '.m4a', '.mp3', '.ogg', '.opus'].includes(ext)) {
    let a = ext === '.wav' ? wavInfo(buf) : null;
    if (!a && hasFfprobe()) a = ffprobeAudio(path);
    if (!a && ext !== '.wav' && !hasFfprobe()) warnings.push(`${name}: 本机没有 ffprobe,无法检查时长/采样率(这一项未验证)`);
    else if (!a) errors.push(`${name}: 不是可解析的音频文件`);
    if (a) {
      Object.assign(facts, { durationMs: a.durationMs, sampleRate: a.sampleRate, channels: a.channels });
      if (constraints.min_duration_ms && a.durationMs < constraints.min_duration_ms) errors.push(`${name}: 时长 ${a.durationMs}ms < ${constraints.min_duration_ms}ms`);
      if (constraints.max_duration_ms && a.durationMs > constraints.max_duration_ms) errors.push(`${name}: 时长 ${a.durationMs}ms > ${constraints.max_duration_ms}ms`);
      if (constraints.min_sample_rate && a.sampleRate < constraints.min_sample_rate) errors.push(`${name}: 采样率 ${a.sampleRate} < ${constraints.min_sample_rate}`);
      if (constraints.channels && a.channels !== constraints.channels) errors.push(`${name}: 声道 ${a.channels} != ${constraints.channels}`);
    }
  }
  if (ext === '.vtt') {
    const { cues, errors: ve } = parseVtt(buf.toString('utf8'));
    errors.push(...ve.map((e) => `${name}: ${e}`)); facts.cues = cues.length;
    if (cues.length === 0) errors.push(`${name}: 没有任何字幕条目`);
    if (constraints.vtt_monotonic) cues.forEach((c, i) => {
      if (c.end <= c.start) errors.push(`${name}: 第 ${i + 1} 条结束时间不晚于开始`);
      if (i && c.start < cues[i - 1].end) errors.push(`${name}: 第 ${i + 1} 条与上一条重叠或倒序`);
      if ([...c.text.replace(/\s/g, '')].length > 34) errors.push(`${name}: 第 ${i + 1} 条超过 34 字(版心上限)`);
    });
  }
  if (ext === '.txt') { if (!buf.toString('utf8').trim()) errors.push(`${name}: 文本为空`); try { new TextDecoder('utf-8', { fatal: true }).decode(buf); } catch { errors.push(`${name}: 不是有效 UTF-8`); } }
  if (ext === '.json') {
    let j; try { j = JSON.parse(buf.toString('utf8')); } catch (e) { errors.push(`${name}: JSON 解析失败:${e.message}`); }
    if (j && constraints.json_schema) {
      const file = { 'parallax-manifest': 'parallax.schema.json', character: 'character.schema.json', 'voice-profile': 'voice-profile.schema.json' }[constraints.json_schema];
      if (file) errors.push(...validate(schema(file), j).map((e) => `${name}: ${e}`)); else errors.push(`${name}: 未知 json_schema ${constraints.json_schema}`);
      facts.json = j;
    }
  }
  return { errors, warnings, facts };
}

export const matchesGlob = (pattern, relPath) =>
  new RegExp('^' + pattern.split('*').map((s) => s.replace(/[.+?^${}()|[\]\\]/g, '\\$&')).join('[^/]*') + '$').test(relPath);

export function listFiles(dir, base = dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? listFiles(join(dir, e.name), base) : [join(dir, e.name).slice(base.length + 1).split('\\').join('/')]);
}

/** 检查整个 inbox/<task_id>/ 对照任务单。返回 {errors, warnings, files:[{path,role,facts}], delivery}。 */
export function checkDelivery(task, dir) {
  const errors = [], warnings = [], out = [];
  if (!existsSync(dir)) return { errors: [`交付目录不存在:${dir}`], warnings, files: [] };
  const present = listFiles(dir).filter((f) => f !== 'delivery.json');
  let delivery = null;
  if (!existsSync(join(dir, 'delivery.json'))) errors.push('缺少 delivery.json(来源与授权声明)');
  else {
    try { delivery = JSON.parse(readFileSync(join(dir, 'delivery.json'), 'utf8')); } catch (e) { errors.push(`delivery.json 解析失败:${e.message}`); }
    if (delivery) {
      errors.push(...validate(schema('delivery.schema.json'), delivery).map((e) => `delivery.json ${e}`));
      if (delivery.task_id && delivery.task_id !== task.task_id) errors.push(`delivery.json task_id ${delivery.task_id} != ${task.task_id}`);
      const banned = task.rights_requirements.forbidden || [];
      const o = `${delivery.rights?.origin || ''} ${delivery.rights?.license || ''}`;
      for (const b of banned) if (b && o.includes(b)) errors.push(`delivery.json 授权/来源含禁止项「${b}」`);
      for (const k of task.rights_requirements.must_provide || []) {
        const v = delivery.rights?.[k];
        if (delivery.rights && (!v || (Array.isArray(v) && v.length === 0))) errors.push(`delivery.json rights.${k} 必填但为空`);
      }
      if (delivery.placeholder === true) warnings.push('交付声明为占位素材:只能以 not_for_release 登记');
    }
  }
  const claimed = new Set();
  let canvas = null;
  const manifest = present.find((f) => /(^|\/)(parallax|manifest)\.json$/.test(f));
  if (manifest) try { const j = JSON.parse(readFileSync(join(dir, manifest), 'utf8')); canvas = j.canvas || null; } catch { /* 下面会报 */ }
  for (const d of task.deliverables) {
    const matches = present.filter((f) => !claimed.has(f) && matchesGlob(d.filename.includes('/') ? d.filename : d.filename, f) && d.formats.includes(extname(f).slice(1).toLowerCase()));
    matches.forEach((f) => claimed.add(f));
    const min = d.min_count ?? (d.required ? 1 : 0), max = d.max_count ?? Infinity;
    if (matches.length < min) errors.push(`交付物「${d.role}」(${d.filename}) 需要至少 ${min} 个,实际 ${matches.length}`);
    if (matches.length > max) errors.push(`交付物「${d.role}」(${d.filename}) 最多 ${max} 个,实际 ${matches.length}`);
    for (const f of matches) {
      const r = checkFile(join(dir, f), d.constraints || {}, { canvas });
      errors.push(...r.errors); warnings.push(...r.warnings);
      out.push({ path: f, role: d.role, facts: r.facts });
    }
  }
  for (const f of present) if (!claimed.has(f)) warnings.push(`多余文件(任务单未要求):${f}`);
  // 视差:清单里引用的层文件必须存在且被交付
  const pj = out.find((f) => f.role === 'entry' && f.facts.json?.layers && f.facts.json?.poster);
  if (pj) { const m = pj.facts.json; for (const f of [...m.layers.map((l) => l.file), m.poster]) if (!present.includes(f)) errors.push(`${pj.path} 引用的文件未交付:${f}`); }
  // 角色:引用的层文件必须存在(复用 character-check 的完整逻辑留给 publish 前的专项检查)
  return { errors, warnings, files: out, delivery };
}
