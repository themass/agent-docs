import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
export const read = rel => JSON.parse(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'));
export const bundle = () => read('../../runtime/contracts/sample.chun-wang.json');
export const pack = () => read('../../runtime/contracts/demo/pack.chun-wang.json');
export const memKv = () => { const m = new Map(); return { get: k => (m.has(k) ? JSON.parse(m.get(k)) : null), set: (k, v) => { m.set(k, JSON.stringify(v)); return true; }, remove: k => m.delete(k), keys: () => [...m.keys()], clearAll: () => m.clear() }; };
