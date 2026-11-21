/**
 * One call: ask(). Tries the agent service (8s); on any failure it answers from the bundle on the device
 * (data/local-help.js) and says so (`source: 'local'`). The page never waits on, or depends on, the agent.
 * The learner's typed words go ONLY to the agent's /turn, and only for free_text / evaluate_retell.
 */
import { localTurn } from './local-help.js';

export function createAgent({ base, fetchImpl = globalThis.fetch?.bind(globalThis), getAuth = () => null, timeoutMs = 8000 }) {
  async function ask({ bundleHash, workId, step, action, args = {}, index, pack }) {
    const body = { bundle_hash: bundleHash, work_id: workId, step, action,
      args: { layer: args.layer ?? null, line_seq: args.line_seq ?? null, ref: args.ref ?? null, text: args.text ?? null } };
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeoutMs);
    try {
      const token = getAuth();
      const res = await fetchImpl(`${base}/turn`, { method: 'POST', credentials: 'omit', signal: ctl.signal,
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify(body) });
      if (!res.ok) throw new Error(`agent ${res.status}`);
      const out = await res.json();
      return { ...out, via: 'agent' };
    } catch (e) {
      const reason = e?.name === 'AbortError' ? 'timeout' : 'unavailable';
      return { ...localTurn({ action, step, args, index, pack }), via: 'local', degraded_reason: reason };
    } finally { clearTimeout(timer); }
  }
  return { ask };
}
