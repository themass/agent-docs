// 电脑的出手时机（spec §20.3「思考时间」）。纯函数式：时间由调用方通过 now 传入，
// 不碰 socket、定时器或 Date.now()。

import {
  autoPlace,
  type BotDifficulty,
  type ClientMessage,
  type GameView,
  type RuleSet,
} from '@plane-duel/shared'
import { chooseShot } from './brain'

/** 每个新决策点的思考时间范围（毫秒）。 */
export const BOT_THINK_MS: readonly [number, number] = [1200, 3500]
/** 最晚在截止前这么久出手。 */
export const BOT_DEADLINE_MARGIN_MS = 1000

export interface BotBrainLike {
  poll(view: GameView, rules: RuleSet, now: number): ClientMessage | null
}

export class BotDriver implements BotBrainLike {
  /** 当前计划：决策点键、计划出手时间、制定计划时的 deadlineAt。 */
  private plan: { key: string; actAt: number; deadlineAt: number | null } | null = null
  /** 已出过手的键。键消失（无决策点）时清除。 */
  private doneKey: string | null = null

  constructor(
    readonly playerId: string,
    readonly difficulty: BotDifficulty,
    private readonly rng: () => number,
  ) {}

  poll(view: GameView, rules: RuleSet, now: number): ClientMessage | null {
    const key = this.decisionKey(view)
    if (key === null) {
      this.plan = null
      this.doneKey = null
      return null
    }
    if (key === this.doneKey) return null

    if (!this.plan || this.plan.key !== key || this.plan.deadlineAt !== view.deadlineAt) {
      this.plan = { key, actAt: this.scheduleAt(now, view.deadlineAt), deadlineAt: view.deadlineAt }
    }
    if (now < this.plan.actAt) return null

    this.doneKey = key
    this.plan = null
    return this.act(key, view, rules)
  }

  private decisionKey(view: GameView): string | null {
    if (view.phase === 'placing') {
      return view.you.planes.length === 0 ? 'place' : null
    }
    if (view.phase !== 'playing') return null // paused / finished
    if (view.mode === 'duel') {
      return view.turn === this.playerId ? `turn:${view.you.shots.length}` : null
    }
    if (!view.you.alive || view.you.submitted || view.round === null) return null
    return `round:${view.round}`
  }

  private scheduleAt(now: number, deadlineAt: number | null): number {
    const [lo, hi] = BOT_THINK_MS
    let actAt = now + lo + this.rng() * (hi - lo)
    if (deadlineAt !== null) actAt = Math.min(actAt, deadlineAt - BOT_DEADLINE_MARGIN_MS)
    return Math.max(actAt, now)
  }

  private act(key: string, view: GameView, rules: RuleSet): ClientMessage | null {
    if (key === 'place') {
      return { type: 'placePlane', planes: autoPlace(rules.boardSize, rules.planeCount, this.rng) }
    }
    const cell = chooseShot(view, rules, this.difficulty, this.rng)
    return cell ? { type: 'fire', row: cell.row, col: cell.col } : null
  }
}
