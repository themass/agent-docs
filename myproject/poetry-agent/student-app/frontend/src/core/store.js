/**
 * Observable app state. Only the learner's preferences, the anonymous device credential and the
 * per-poem progress are persisted; everything else (network, data source) is session-only.
 */
// No grade/audience preference: one telling for every reader (product decision 2026-11-12).
// An `audience` left in old saved prefs is simply not read back.
const PREF_KEYS = ['mediaOff', 'pinyin', 'fontScale', 'consent'];

export function createStore(kv) {
  const saved = kv.get('prefs') || {};
  const state = {
    mediaOff: saved.mediaOff === true,
    pinyin: saved.pinyin === true,                                      // a reading aid the reader turns on; off by default
    fontScale: clampScale(saved.fontScale),
    consent: saved.consent === 'yes' || saved.consent === 'no' ? saved.consent : null,   // null = not asked yet
    device: kv.get('device') || null,
    progress: kv.get('progress') || {},
    source: 'live',                                                     // live | demo-fixture | offline-cache
    net: { online: true, weak: false },
  };
  const subs = new Set();
  const emit = key => subs.forEach(fn => { try { fn(key, state); } catch { /* a bad subscriber must not break the rest */ } });

  return {
    get: key => state[key],
    all: () => state,
    set(key, value) {
      if (key === 'fontScale') value = clampScale(value);
      state[key] = value;
      if (PREF_KEYS.includes(key)) kv.set('prefs', Object.fromEntries(PREF_KEYS.map(k => [k, state[k]])));
      else if (key === 'device') { if (value) kv.set('device', value); else kv.remove('device'); }
      else if (key === 'progress') kv.set('progress', value);
      emit(key);
    },
    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
    pinyinOn: () => state.pinyin === true,
    /** Progress is where the learner stopped; there is no score, no streak, no percentage. */
    progressOf: workId => state.progress[workId] || null,
    patchProgress(workId, patch) {
      const cur = state.progress[workId] || { enteredAt: patch.enteredAt || new Date().toISOString(), visited: [] };
      this.set('progress', { ...state.progress, [workId]: { ...cur, ...patch } });
    },
    clearProgress() { this.set('progress', {}); },
  };
}

function clampScale(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(1.6, Math.max(0.9, n)) : 1;
}

/** Synchronous key-value over localStorage with a memory fallback (private mode / quota / SSR). */
export function createKv(storage, prefix = 'xs.') {
  const mem = new Map();
  const safe = (fn, dflt) => { try { return fn(); } catch { return dflt; } };
  return {
    get(key) {
      const raw = safe(() => storage?.getItem(prefix + key), null) ?? mem.get(key) ?? null;
      if (raw == null) return null;
      try { return JSON.parse(raw); } catch { return null; }
    },
    set(key, value) {
      const raw = JSON.stringify(value);
      mem.set(key, raw);
      return safe(() => { storage?.setItem(prefix + key, raw); return true; }, false);
    },
    remove(key) { mem.delete(key); safe(() => storage?.removeItem(prefix + key)); },
    keys() {
      const out = new Set(mem.keys());
      safe(() => { for (let i = 0; i < (storage?.length || 0); i++) { const k = storage.key(i); if (k?.startsWith(prefix)) out.add(k.slice(prefix.length)); } });
      return [...out];
    },
    clearAll() { for (const k of this.keys()) this.remove(k); },
  };
}
