/**
 * Learning events: structured behaviour only, no free text, ever. validateEvent mirrors the server's
 * EventValidator rule for rule (a test compares the two vocabularies); the server re-checks anyway.
 * Queue is local and capped; a failed send keeps it, a refused batch (400) drops it so it cannot wedge the queue.
 */
import { ASK_ACTIONS, DEGRADE_REASONS, EVENT_KINDS, FALLBACK_REASONS, ID, LAYERS, MAX_DWELL_MS,
  MAX_EVENTS_PER_BATCH, MAX_LINE_SEQ, RETELL_LENGTHS, STEPS } from '../core/vocab.js';

export function retellLength(text) {
  const n = [...String(text || '')].length;
  return n <= 20 ? 'len_0_20' : n <= 60 ? 'len_21_60' : 'len_61_plus';
}

export function validateEvent(e) {
  if (!e || !ID.test(e.workId || '')) return 'workId';
  if (!STEPS.includes(e.step)) return 'step';
  if (!EVENT_KINDS.includes(e.kind)) return 'kind';
  const hasRef = e.ref != null, hasMs = e.ms != null;
  switch (e.kind) {
    case 'step_enter': case 'step_skip': return hasRef || hasMs ? 'extra' : null;
    case 'step_leave': return hasRef || !(Number.isInteger(e.ms) && e.ms >= 0 && e.ms <= MAX_DWELL_MS) ? 'ms' : null;
    case 'layer_open': return e.step === 'arrive' && LAYERS.includes(e.ref) && !hasMs ? null : 'ref';
    case 'line_tap': return (e.step === 'read' || e.step === 'return') && /^[1-9][0-9]?$/.test(String(e.ref))
      && Number(e.ref) <= MAX_LINE_SEQ && !hasMs ? null : 'ref';
    case 'ask': return ASK_ACTIONS.includes(e.ref) && !hasMs ? null : 'ref';
    case 'retell_submit': return e.step === 'recite' && RETELL_LENGTHS.includes(e.ref) && !hasMs ? null : 'ref';
    case 'media_degraded': return DEGRADE_REASONS.includes(e.ref) && !hasMs ? null : 'ref';
    case 'agent_fallback': return FALLBACK_REASONS.includes(e.ref) && !hasMs ? null : 'ref';
    default: return 'kind';
  }
}

export function createTracker({ api, kv, getDevice, allowed, now = () => new Date(), setTimer = setTimeout }) {
  const KEY = 'q:events';
  let timer = null, flushing = false;

  const queue = () => kv.get(KEY) || [];
  function schedule() { if (!timer) timer = setTimer(() => { timer = null; flush(); }, 4000); }

  function track(event) {
    if (!allowed() || validateEvent(event)) return false;     // before consent nothing is even queued
    const q = queue();
    q.push({ ...event, at: now().toISOString() });
    kv.set(KEY, q.slice(-200));
    schedule();
    return true;
  }

  async function flush() {
    if (flushing || !allowed()) return;
    flushing = true;
    const device = await getDevice();
    if (!device) { flushing = false; return; }
    try {
      for (let q = queue(); q.length; q = queue()) {
        const batch = q.slice(0, MAX_EVENTS_PER_BATCH);
        try { await api.post('/devices/me/events', batch, { auth: true }); }
        catch (e) {
          if (e.kind === 'http' && e.status === 400) { kv.set(KEY, q.slice(batch.length)); continue; }
          break;                                              // network or auth trouble: keep the queue, try later
        }
        kv.set(KEY, q.slice(batch.length));
      }
    } finally { flushing = false; }
  }

  return { track, flush, pending: () => queue().length, discard: () => kv.remove(KEY) };
}

/** Registers an anonymous device on first need and returns its credential. */
export async function ensureDevice({ api, store }) {
  const have = store.get('device');
  if (have?.deviceKey) return have;
  const { data } = await api.post('/devices', undefined);
  const device = { deviceId: data.deviceId, deviceKey: data.deviceKey };
  store.set('device', device);
  return device;
}
