import type { Storage } from '@xuexi/scene-runtime';

/**
 * IndexedDB-backed asset cache with a byte quota. Same contract a Capacitor shell satisfies by
 * writing into the app sandbox — the kernel cannot tell the difference, which is the point.
 */
export function createWebStorage(dbName = 'xuexi-assets', quotaBytes = 300 * 1024 * 1024): Storage {
  const memory = new Map<string, Uint8Array>();                 // test/SSR fallback, never the product path
  const order: string[] = [];

  const touch = (key: string) => {
    const i = order.indexOf(key);
    if (i >= 0) order.splice(i, 1);
    order.unshift(key);
  };

  return {
    async put(key, bytes) {
      touch(key);
      memory.set(key, bytes);
      if (typeof indexedDB === 'undefined') return;
      const db = await open(dbName);
      await txPut(db, key, bytes);
      if (await usageOf(db, quotaBytes) > quotaBytes) await trim(db, quotaBytes);
    },
    async get(key) {
      if (typeof indexedDB !== 'undefined') {
        const hit = await txGet(await open(dbName), key);
        if (hit) { touch(key); return hit; }
      }
      touch(key);
      return memory.get(key) ?? null;
    },
    async usage() {
      if (typeof navigator !== 'undefined' && navigator.storage?.estimate) {
        const e = await navigator.storage.estimate();
        if (typeof e.usage === 'number') return e.usage;
      }
      return [...memory.values()].reduce((n, b) => n + b.byteLength, 0);
    },
    async evict(keys) {
      if (typeof indexedDB !== 'undefined') await txDelete(await open(dbName), keys);
      for (const k of keys) { memory.delete(k); const i = order.indexOf(k); if (i >= 0) order.splice(i, 1); }
    },
    async keys() { return [...order]; },                          // access order = LRU order
  };
}

function open(name: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(name, 1);
    req.onupgradeneeded = () => { if (!req.result.objectStoreNames.contains('assets')) req.result.createObjectStore('assets'); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
const store = (db: IDBDatabase) => db.transaction('assets', 'readwrite').objectStore('assets');
const txPut = (db: IDBDatabase, key: string, bytes: Uint8Array) =>
  new Promise<void>((res, rej) => { const r = store(db).put(bytes, key); r.onsuccess = () => res(); r.onerror = () => rej(r.error); });
const txGet = (db: IDBDatabase, key: string) =>
  new Promise<Uint8Array | null>((res, rej) => { const r = db.transaction('assets', 'readonly').objectStore('assets').get(key); r.onsuccess = () => res((r.result as Uint8Array) ?? null); r.onerror = () => rej(r.error); });
const txDelete = (db: IDBDatabase, keys: string[]) =>
  new Promise<void>(res => { const s = store(db); keys.forEach(k => s.delete(k)); db.transaction('assets', 'readwrite').oncomplete = () => res(); });
/** Bytes, not row count: the quota is a byte quota (300MB), so this must measure bytes. */
async function usageOf(db: IDBDatabase, _quota: number): Promise<number> {
  return new Promise(res => {
    const os = db.transaction('assets', 'readonly').objectStore('assets');
    const all = os.openCursor();
    let total = 0;
    all.onsuccess = () => {
      const c = all.result;
      if (c) { total += (c.value as Uint8Array).byteLength; c.continue(); } else { res(total); }
    };
    all.onerror = () => res(Number.MAX_SAFE_INTEGER);       // unknown usage must be treated as "over quota"
  });
}
/** Eviction order is decided by the kernel (evictToQuota + LRU keys), so trim() stays a no-op here. */
async function trim(db: IDBDatabase, _quota: number) {}
