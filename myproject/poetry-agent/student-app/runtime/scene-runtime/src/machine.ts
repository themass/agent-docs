/**
 * The five-step state machine: 读 → 到 → 见 → 回 → 诵.
 *
 * It is a state machine, not a funnel (rule R12): every step can be entered, skipped and revisited,
 * nothing is scored. A learner who jumps straight to 诵 has not "broken" the flow — that is the flow.
 * Framework-free on purpose: React/Vue/Capacitor shells all drive this same object.
 */
import { STEPS, type SceneBundle, type StepId } from './bundle.ts';

export type RuntimeMode = 'loading' | 'ready' | 'degraded' | 'offline' | 'asking' | 'recording';

export interface MachineState {
  current: StepId;
  visited: StepId[];
  mode: RuntimeMode;
  /** Which assets failed and what they fell back to — surfaced in UI, never hidden. */
  degraded: { assetId: string; to: string; reason: string }[];
}

export class SceneMachine {
  private state: MachineState;
  private bundle: SceneBundle;

  constructor(bundle: SceneBundle, entry: StepId = 'read') {
    if (!STEPS.includes(entry)) throw new Error(`unknown entry step: ${entry}`);
    if (STEPS.some(s => !bundle.steps.some(b => b.step === s)))
      throw new Error('bundle is missing one of the five steps');
    this.bundle = bundle;
    this.state = { current: entry, visited: [entry], mode: 'loading', degraded: [] };
  }

  get snapshot(): Readonly<MachineState> { return this.state; }

  step(id: StepId, reason: 'user' | 'next' | 'back' = 'user'): MachineState {
    const target = this.bundle.steps.find(s => s.step === id);
    if (!target) throw new Error(`bundle has no ${id} step`);
    if (reason === 'next' && target.skip_allowed !== true)
      throw new Error(`${id} declares skip_allowed:false — such a bundle must not compile`);
    if (reason === 'back' && target.back_allowed !== true)
      throw new Error(`${id} declares back_allowed:false — a learner must always be able to go back`);
    this.state.current = id;
    if (!this.state.visited.includes(id)) this.state.visited.push(id);
    if (this.state.mode === 'loading') this.state.mode = 'ready';
    return this.state;
  }

  next(): MachineState {
    const i = STEPS.indexOf(this.state.current);
    return i < STEPS.length - 1 ? this.step(STEPS[i + 1], 'next') : this.state;
  }

  back(): MachineState {
    const i = this.state.visited.indexOf(this.state.current);
    return i > 0 ? this.step(this.state.visited[i - 1], 'back') : this.state;
  }

  /** Ask is a mode, not a step: the learner can ask while staying wherever they are. */
  enter(mode: RuntimeMode): MachineState { this.state.mode = mode; return this.state; }

  reportDegraded(assetId: string, to: string, reason: string): void {
    this.state.mode = this.state.mode === 'loading' ? 'ready' : this.state.mode;
    if (!this.state.degraded.some(d => d.assetId === assetId))
      this.state.degraded.push({ assetId, to, reason });
  }

  /** What the learner is told the round does NOT cover. Never invented in the client. */
  coverageNotice(): string { return this.bundle.coverage_notice; }
}
