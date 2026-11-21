/**
 * Reads with an offline fallback. Network first; a good answer is cached; when the network fails
 * (or the server errors) the last good copy is returned and the source is reported as offline-cache so
 * the UI says so. A 404 deletes the cached copy: content that was withdrawn must not come back from a cache.
 * Bundles are the exception: immutable by hash, so cache first.
 */
const INDEX_KEY = 'c:index';
const MAX_ENTRIES = 60;

export function createRepo({ api, kv, onSource = () => {} }) {
  function remember(key) {
    const idx = (kv.get(INDEX_KEY) || []).filter(k => k !== key);
    idx.push(key);
    while (idx.length > MAX_ENTRIES) kv.remove(idx.shift());
    kv.set(INDEX_KEY, idx);
  }
  function forget(key) { kv.remove(key); kv.set(INDEX_KEY, (kv.get(INDEX_KEY) || []).filter(k => k !== key)); }

  async function netFirst(path, { raw = false, key = `c:${path}` } = {}) {
    try {
      const { data, source } = await api.get(path, { raw });
      if (kv.set(key, data)) remember(key);
      onSource(source);
      return data;
    } catch (e) {
      if (e.kind === 'http' && e.status === 404) { forget(key); throw e; }
      if (e.kind === 'http' && e.status >= 400 && e.status < 500) throw e;
      const cached = kv.get(key);
      if (cached == null) throw e;
      onSource('offline-cache');
      return cached;
    }
  }

  return {
    config: () => netFirst('/config'),
    works: () => netFirst('/works'),
    overview: () => netFirst('/overview'),
    timeline: (from, to, limit = 100) => netFirst(`/timeline?fromYear=${from}&toYear=${to}&limit=${limit}`),
    pack: workId => netFirst(`/works/${encodeURIComponent(workId)}/pack`),
    /** null = this work has no published lesson yet ("场景整理中"), which is a normal state, not an error. */
    async lesson(workId) {
      try { return await netFirst(`/works/${encodeURIComponent(workId)}/lesson`); }
      catch (e) { if (e.kind === 'http' && e.status === 404) return null; throw e; }
    },
    async bundle(hash) {
      const key = `b:${hash}`;
      const hit = kv.get(key);
      if (hit) return hit;
      const { data } = await api.get(`/bundles/${encodeURIComponent(hash)}`, { raw: true });
      kv.set(key, data);
      const ids = (kv.get('b:index') || []).filter(h => h !== hash);
      ids.push(hash);
      while (ids.length > 6) kv.remove(`b:${ids.shift()}`);
      kv.set('b:index', ids);
      return data;
    },
    async assets() {
      const rows = await netFirst('/assets?limit=200');
      return new Map(rows.map(r => [r.id, r]));
    },
    citations: claimId => api.get(`/claims/${encodeURIComponent(claimId)}/citations`).then(r => r.data),
    clearCache() { for (const k of kv.keys()) if (k.startsWith('c:') || k.startsWith('b:')) kv.remove(k); },
  };
}
