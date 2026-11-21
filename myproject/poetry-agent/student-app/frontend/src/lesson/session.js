/**
 * A lesson in progress: the shared kernel's five-step machine plus what the app does around it
 * (events, resume point). Free movement is the rule: any step can be entered, skipped, revisited;
 * nothing is scored, nothing is locked. The machine throws if a bundle lacks one of the five steps,
 * and the view turns that into "这一课还没准备好" instead of a half lesson.
 */
import { SceneMachine, STEPS } from '../kernel/index.js';

export function createSession({ bundle, workId, store, track, now = () => Date.now(), entry = 'read' }) {
  const machine = new SceneMachine(bundle, STEPS.includes(entry) ? entry : 'read');
  const opened = new Set();
  let enteredAt = now();
  let current = machine.snapshot.current;
  const subs = new Set();

  const emit = () => subs.forEach(fn => fn(current));
  const ev = (step, kind, extra = {}) => track({ workId, step, kind, ...extra });
  const save = () => store.patchProgress(workId, { lastStep: current, visited: [...machine.snapshot.visited] });

  function leave(kind) {
    const ms = Math.max(0, Math.min(3_600_000, now() - enteredAt));
    if (kind === 'step_skip') ev(current, 'step_skip'); else ev(current, 'step_leave', { ms });
  }
  function move(step, how) {
    if (step === current) return current;
    leave(how === 'skip' ? 'step_skip' : 'step_leave');
    machine.step(step, how === 'back' ? 'back' : how === 'skip' ? 'next' : 'user');
    current = step;
    enteredAt = now();
    ev(current, 'step_enter');
    save();
    emit();
    return current;
  }
  ev(current, 'step_enter');
  save();

  return {
    get step() { return current; },
    get visited() { return [...machine.snapshot.visited]; },
    get opened() { return new Set(opened); },
    go: step => move(step, 'user'),
    next() { const i = STEPS.indexOf(current); return i < STEPS.length - 1 ? move(STEPS[i + 1], 'user') : current; },
    prev() { const i = STEPS.indexOf(current); return i > 0 ? move(STEPS[i - 1], 'back') : current; },
    skip() { const i = STEPS.indexOf(current); return i < STEPS.length - 1 ? move(STEPS[i + 1], 'skip') : current; },
    openLayer(layer) { if (!opened.has(layer)) { opened.add(layer); ev('arrive', 'layer_open', { ref: layer }); } },
    /** True only the first time and only if some layer was never opened: a single gentle nudge, never a gate. */
    shouldNudge(totalLayers) {
      if (this._nudged || current !== 'arrive' || opened.size >= totalLayers) return false;
      this._nudged = true;
      return true;
    },
    tapLine(seq) { if (current === 'read' || current === 'return') ev(current, 'line_tap', { ref: String(seq) }); },
    ask(action) { ev(current, 'ask', { ref: action }); },
    exit() { leave('step_leave'); save(); },
    subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
    coverageNotice: () => machine.coverageNotice(),
  };
}
