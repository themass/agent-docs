// 登记簿库:hash、文件索引、登记项构造、跨项检查(镜像 Java PoetryMediaService.validate/chain 与编译规则 R4/R9/R10)。
import { createHash } from 'node:crypto';
import { readFileSync, statSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { validate } from './jsonschema.mjs';

export const PRODUCTION_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const PUBLISHED = join(PRODUCTION_ROOT, 'published');
export const REGISTRY_PATH = join(PUBLISHED, 'registry.json');
export const LEVELS = ['L0', 'L1', 'L2', 'L3', 'L4'];
export const KINDS = ['illustration', 'map', 'character', 'audio', 'voice', 'subtitle', 'video'];
export const ID_RE = /^[a-z0-9][a-z0-9._-]{0,63}$/;

export const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');
export const readJson = (p) => JSON.parse(readFileSync(p, 'utf8'));
export const schema = (name) => readJson(join(PRODUCTION_ROOT, 'contracts', name));
export const levelRank = (l) => LEVELS.indexOf(l);

/** 多文件素材的 hash:按 path 排序后的 "<path>\t<sha256>\n" 拼接再取 sha256。 */
export function filesIndexHash(files) {
  const lines = [...files].sort((a, b) => (a.path < b.path ? -1 : 1)).map((f) => `${f.path}\t${f.sha256}\n`).join('');
  return sha256(Buffer.from(lines, 'utf8'));
}

/** 读取 baseDir 下的若干相对路径,返回 registry.files 项。 */
export function describeFiles(baseDir, relPaths, extra = {}) {
  return relPaths.map((p) => {
    const abs = join(baseDir, p);
    const buf = readFileSync(abs);
    const format = (p.split('.').pop() || '').toLowerCase();
    return { path: relative(PUBLISHED, abs).split('\\').join('/'), sha256: sha256(buf), bytes: buf.length, format, ...(extra[p] || {}) };
  });
}

/** 由文件清单计算 hash/hash_scheme/bytes。单文件→文件 sha256;多文件→索引 hash。 */
export function fingerprint(files) {
  const bytes = files.reduce((n, f) => n + f.bytes, 0);
  if (files.length === 1) return { hash: files[0].sha256, hash_scheme: 'file-sha256', bytes };
  return { hash: filesIndexHash(files), hash_scheme: 'files-index-sha256', bytes };
}

export function loadRegistry(path = REGISTRY_PATH) {
  if (!existsSync(path)) return { schema_version: '1.0', generated_at: new Date(0).toISOString(), root: 'published/', assets: [] };
  return readJson(path);
}

export function saveRegistry(reg, path = REGISTRY_PATH) {
  reg.generated_at = new Date().toISOString();
  reg.assets.sort((a, b) => (a.asset_id < b.asset_id ? -1 : 1));
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(reg, null, 2) + '\n');
}

export function upsert(reg, entry) {
  const i = reg.assets.findIndex((a) => a.asset_id === entry.asset_id);
  if (i >= 0) reg.assets[i] = entry; else reg.assets.push(entry);
  return reg;
}

/** 检查 registry:schema + 文件真实存在且 hash/bytes 一致 + Java 的跨项规则。返回 {errors, warnings}。 */
export function checkRegistry(reg, { publishedDir = PUBLISHED, verifyFiles = true } = {}) {
  const errors = [], warnings = [];
  errors.push(...validate(schema('asset-registry.schema.json'), reg));
  const byId = new Map();
  const hashOwner = new Map();
  for (const a of reg.assets || []) {
    if (byId.has(a.asset_id)) errors.push(`${a.asset_id}: asset_id 重复`);
    byId.set(a.asset_id, a);
  }
  for (const a of reg.assets || []) {
    const id = a.asset_id;
    if (!ID_RE.test(id || '')) continue; // schema 已报
    if (hashOwner.has(a.hash) && hashOwner.get(a.hash) !== id) errors.push(`${id}: hash 与 ${hashOwner.get(a.hash)} 相同(Java: hash already used by another asset)`);
    hashOwner.set(a.hash, id);
    if (a.level === 'L0') {
      if (a.fallback_asset_id) errors.push(`${id}: L0 是地板,不得有 fallback_asset_id`);
    } else {
      if (!a.fallback_asset_id) errors.push(`${id}: 非 L0 素材必须有 fallback_asset_id`);
      else if (a.fallback_asset_id === id) errors.push(`${id}: 不能降级到自己`);
      else {
        const low = byId.get(a.fallback_asset_id);
        if (!low) errors.push(`${id}: fallback ${a.fallback_asset_id} 未登记(先建低一级)`);
        else if (levelRank(low.level) >= levelRank(a.level)) errors.push(`${id}: fallback 必须严格更低一级:${a.level} -> ${low.level}`);
      }
    }
    // 链:必须在 ≤10 步内到达 L0,无环
    const seen = new Set(); let cur = a, reached = a.level === 'L0';
    while (cur && !reached && seen.size <= 10) {
      if (seen.has(cur.asset_id)) { errors.push(`${id}: 降级链成环`); break; }
      seen.add(cur.asset_id);
      cur = cur.fallback_asset_id ? byId.get(cur.fallback_asset_id) : null;
      reached = !!cur && cur.level === 'L0';
    }
    if (!reached && !errors.some((e) => e.startsWith(`${id}:`) && /成环|未登记/.test(e))) errors.push(`${id}: 降级链没有到达 L0(文字)`);
    if (a.uri && !a.files?.some((f) => f.path === a.uri)) errors.push(`${id}: uri ${a.uri} 不在 files[] 中`);
    if (a.files) {
      const sum = a.files.reduce((n, f) => n + f.bytes, 0);
      if (sum !== a.bytes) errors.push(`${id}: bytes ${a.bytes} != files 之和 ${sum}`);
      const fp = fingerprint(a.files);
      if (fp.hash !== a.hash || fp.hash_scheme !== a.hash_scheme) errors.push(`${id}: hash/hash_scheme 与 files[] 不一致`);
      if (verifyFiles) for (const f of a.files) {
        const abs = join(publishedDir, f.path);
        if (!existsSync(abs)) { errors.push(`${id}: 文件不存在 ${f.path}`); continue; }
        const buf = readFileSync(abs);
        if (buf.length !== f.bytes) errors.push(`${id}: ${f.path} 字节数变了(登记 ${f.bytes},实际 ${buf.length})`);
        else if (sha256(buf) !== f.sha256) errors.push(`${id}: ${f.path} 内容 hash 变了`);
      }
    }
    if (a.placeholder?.is_placeholder && !a.placeholder.not_for_release) warnings.push(`${id}: 占位素材未标 not_for_release`);
  }
  return { errors, warnings };
}
