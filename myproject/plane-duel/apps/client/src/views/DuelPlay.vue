<script setup lang="ts">
/**
 * 2 人对决界面（P0 的 Play 改接 v2 仓库）。
 * 规则：边长 ≥ 12 时两步开炮——点格子只是选中，再按「开炮」才发出。
 */
import { computed, ref, watch } from 'vue'
import { cellKey, type Cell } from '@plane-duel/shared'
import BoardGrid from '../components/BoardGrid.vue'
import Countdown from '../components/Countdown.vue'
import { buildBoardCells, duelHintKeys } from '../board-model'
import { hasBots, seatLabel } from '../lobby-model'
import { needsTwoStep } from '../place-model'
import { fx, haptics } from '../fx/fx'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const s = props.store.state

const table = computed(() => s.table!)
const rules = computed(() => table.value.rules)
const game = computed(() => s.game!)
const opponent = computed(() => game.value.others[0])

const opponentSeat = computed(() =>
  opponent.value === undefined ? null : (table.value.seats.find((x) => x?.playerId === opponent.value!.playerId) ?? null),
)
const opponentNick = computed(() => (opponentSeat.value === null ? '对手' : seatLabel(opponentSeat.value)))
const withBots = computed(() => hasBots(table.value))

const myTurn = computed(() => game.value.phase === 'playing' && game.value.turn === s.playerId)
const paused = computed(() => game.value.phase === 'paused')
const finished = computed(() => game.value.phase === 'finished')
const twoStep = computed(() => needsTwoStep(rules.value, 'duel'))

/** 乐观禁用：发出 fire 到收到回包之间，该格不可再点（防连点，Review Focus #1） */
const pendingKey = ref<string | null>(null)
watch(
  () => [game.value.you.shots.length, s.error] as const,
  () => (pendingKey.value = null),
)

const selected = ref<Cell | null>(null)
const selectedKey = computed(() => (selected.value ? cellKey(selected.value) : null))

const enemyCells = computed(() =>
  buildBoardCells({
    boardSize: rules.value.boardSize,
    shots: game.value.you.shots,
    planes: [],
    showPlane: false,
  }),
)
const ownCells = computed(() =>
  buildBoardCells({
    boardSize: rules.value.boardSize,
    shots: game.value.you.incoming,
    planes: game.value.you.planes,
    showPlane: true,
  }),
)

/** 推理提示：默认关闭，房主禁用时不显示（spec §十二、§19.3） */
const HINT_KEY = 'plane-duel:hint'
const hintOn = ref(localStorage.getItem(HINT_KEY) === '1' && rules.value.hintAllowed)
watch(hintOn, (v) => localStorage.setItem(HINT_KEY, v ? '1' : '0'))
const hintKeys = computed(() => {
  if (!hintOn.value || !rules.value.hintAllowed) return undefined
  // 多架飞机：按飞机分别推理再取并集，跳过已击落的（评审 I6）
  return duelHintKeys(game.value.you.shots, rules.value.boardSize)
})

function send(cell: Cell) {
  pendingKey.value = cellKey(cell)
  fx.play('fire')
  haptics.vibrate('fire')
  props.socket.send({ type: 'fire', row: cell.row, col: cell.col })
}

// P6 手感：出炮回包 → 命中音效 + 分级震动；被打中 → 机身/机头各有反馈；终局 → 胜负音
watch(
  () => game.value.you.shots.length,
  (n, old) => {
    if (n <= old) return
    const shot = game.value.you.shots[n - 1]
    if (shot === undefined) return
    fx.play(shot.result)
    haptics.vibrate(shot.result)
  },
)
watch(
  () => game.value.you.incoming.length,
  (n, old) => {
    if (n <= old) return
    const shot = game.value.you.incoming[n - 1]
    if (shot === undefined || shot.result === 'miss') return
    fx.play(shot.result)
    haptics.vibrate('inbound')
  },
)

function tap(cell: Cell) {
  if (!myTurn.value || pendingKey.value) return
  if (!twoStep.value) return send(cell)
  selected.value = cell
}

function confirmFire() {
  if (!selected.value || !myTurn.value || pendingKey.value) return
  send(selected.value)
  selected.value = null
}

const statusText = computed(() => {
  if (paused.value) return '对手掉线，等待重连'
  return myTurn.value ? '轮到你开炮' : '对手瞄准中…'
})

function colLabel(c: number): string {
  return 'ABCDEFGHIJKLMNOP'[c] ?? String(c + 1)
}
</script>

<template>
  <section class="play">
    <header class="bar" :class="{ mine: myTurn }">
      <span class="status">{{ statusText }}</span>
      <Countdown v-if="!paused" :deadline-at="game.deadlineAt" />
    </header>

    <p v-if="withBots" class="bots-note">{{ table.kind === 'practice' ? '人机练习 · 不计段位' : '本局有电脑补位 · 不计段位' }}</p>

    <div class="board-block">
      <div class="board-title">
        <span>敌方海域 · {{ opponentNick }} · {{ opponent?.planesDestroyed ?? 0 }}/{{ rules.planeCount }} 已击落</span>
        <label v-if="rules.hintAllowed" class="hint-toggle">
          <input v-model="hintOn" type="checkbox" />
          推理提示
        </label>
      </div>
      <BoardGrid
        :board-size="rules.boardSize"
        :cells="enemyCells"
        :disabled="!myTurn"
        :pending-key="pendingKey"
        :hint-keys="hintKeys"
        :selected-key="selectedKey"
        @cell-tap="tap"
      />
    </div>

    <button v-if="twoStep && selected" class="btn primary fire-btn" @click="confirmFire">
      开炮 {{ colLabel(selected.col) }}{{ selected.row + 1 }}
    </button>

    <div class="board-block own">
      <div class="board-title">
        <span>我方海域 · 剩 {{ rules.planeCount - game.you.planesDestroyed }} 架</span>
        <span v-if="game.you.incoming.length" class="muted">
          对手上一炮：{{ colLabel(game.you.incoming.at(-1)!.col) }}{{ game.you.incoming.at(-1)!.row + 1 }}
        </span>
      </div>
      <BoardGrid :board-size="rules.boardSize" :cells="ownCells" disabled />
    </div>
  </section>
</template>

<style scoped>
.play {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.bar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-radius: 12px;
  background: var(--bg-raised);
  border: 1px solid var(--grid-line);
  transition: background-color 200ms ease, border-color 200ms ease;
}
.bar.mine {
  border-color: var(--accent);
  background: rgb(240 160 48 / 0.14);
}
.status {
  font-weight: 700;
  letter-spacing: 0.04em;
}
.bots-note {
  margin: 0;
  text-align: center;
  font-size: 13px;
  color: var(--accent);
}
.board-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  letter-spacing: 0.1em;
  color: var(--ink-soft);
  margin-bottom: 6px;
}
.own :deep(.board-wrap) {
  max-width: 260px;
}
.hint-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.fire-btn {
  position: sticky;
  bottom: 12px;
  z-index: 6;
  box-shadow: 0 6px 20px rgb(0 0 0 / 0.4);
}
</style>
