// 占位生成器的共用部分:读任务单、写 inbox/<task>/、写 delivery.json(明确标注占位)。
import { mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '../..');
export const tasksOf = (poem) => Object.fromEntries(JSON.parse(readFileSync(join(ROOT, 'tasks', poem, 'tasks.json'), 'utf8')).tasks.map((t) => [t.task_id, t]));
export const inbox = (id) => join(ROOT, 'inbox', id);

export function fresh(id) { const d = inbox(id); rmSync(d, { recursive: true, force: true }); mkdirSync(d, { recursive: true }); return d; }
export function put(id, rel, data) { const p = join(inbox(id), rel); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, data); return p; }

export const PLACEHOLDER_LICENSE = '自有占位,不可上线';
export function delivery(id, { generator, origin, extraNotes = '', evidence = [] }) {
  put(id, 'delivery.json', JSON.stringify({
    schema_version: '1.0', task_id: id, delivered_at: new Date().toISOString(), author: 'placeholder-generator',
    rights: { origin, license: PLACEHOLDER_LICENSE, workflow: generator, human_fix: false, author: 'placeholder-generator', evidence,
              notes: `占位素材,代码生成,不可上线。${extraNotes}`.trim() },
    placeholder: true, notes: '占位:让学生端先跑通。正式素材交付后会以同一 asset_id 替换。',
  }, null, 2) + '\n');
}

export function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { encoding: 'utf8', ...opts });
  if (r.status !== 0) throw new Error(`${cmd} ${args.slice(0, 4).join(' ')} 失败:${(r.stderr || '').slice(-300)}`);
  return r;
}

/** 确定性伪随机,保证重复生成得到同样的图。 */
export function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
