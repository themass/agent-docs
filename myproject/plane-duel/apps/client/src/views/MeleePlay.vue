<script setup lang="ts">
/**
 * 3–4 人混战界面（spec §19.9）。
 *
 * 一炮同时落在每个存活对手的棋盘上，所以只有一块「目标棋盘」：
 * 每格 2×2 小槽按座位色显示各对手的结果；上方标签可切到单个对手看大号标记与推理提示。
 * 混战恒为两步开炮：点格子选中，再按「开炮」提交本轮。
 */
import { computed, ref, watch } from 'vue'
import { cellKey, type Cell } from '@plane-duel/shared'
import BoardGrid from '../components/BoardGrid.vue'
import Countdown from '../components/Countdown.vue'
import { buildBoardCells, buildTargetCells, SEAT_COLORS } from '../board-model'
import { peerStatus } from '../lobby-model'
import { fx, haptics } from '../fx/fx'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const s = props.store.state

const table = computed(() => s.table!)
const rules = computed(() => table.value.rules)
const game = computed(() => s.game!)
const me = computed(() => s.playerId)

const seatOf = (playerId: string): number => table.value.seats.findIndex((x) => x?.playerId === playerId)
const colorOf = (playerId: string): string => {
  const i = seatOf(playerId)
  return SEAT_COLORS[i >= 0 ? i : 0]!
}
const nickOf = (playerId: string): string => table.value.seats.find((x) => x?.playerId === playerId)?.nickname ?? '玩家'
const isBot = (playerId: string): boolean => {
  const seat = table.value.seats.find((x) => x?.playerId === playerId)
  return seat !== undefined && seat !== null && seat.bot
}

/** 存活对手（出局的留在 others 里用于结算，但不作为目标） */
const opponents = computed(() =>
  game.value.others.map((o) => ({
    playerId: o.playerId,
    color: colorOf(o.playerId),
    alive: o.alive,
    nickname: isBot(o.playerId) ? `🤖 ${nickOf(o.playerId)}` : nickOf(o.playerId),
    planesDestroyed: o.planesDestroyed,
    status: peerStatus(o),
  })),
)
const aliveOpponents = computed(() => opponents.value.filter((o) => o.alive))

const focus = ref<string | null>(null)
// 聚焦的对手出局后回到合并视图
watch(aliveOpponents, (list) => {
  if (focus.value !== null && !list.some((o) => o.playerId === focus.value)) focus.value = null
})

const HINT_KEY = 'plane-duel:hint'
const hintOn = ref(localStorage.getItem(HINT_KEY) === '1' && rules.value.hintAllowed)
watch(hintOn, (v) => localStorage.setItem(HINT_KEY, v ? '1' : '0'))

const targetCells = computed(() =>
  buildTargetCells({
    boardSize: rules.value.boardSize,
    shots: game.value.you.shots,
    opponents: opponents.value,
    focus: focus.value,
    hintFor: hintOn.value && rules.value.hintAllowed ? focus.value : null,
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

// M1：本回合是否已开炮以服务端为准（刷新后仍在），本地只留选中格
const selected = ref<Cell | null>(null)
const selectedKey = computed(() => (selected.value ? cellKey(selected.value) : null))
const playing = computed(() => game.value.phase === 'playing')
const paused = computed(() => game.value.phase === 'paused')
const iAmAlive = computed(() => game.value.you.alive)
const submitted = computed(() => game.value.you.submitted)
const canFire = computed(() => playing.value && iAmAlive.value && !submitted.value)

// 新一轮开始（round 变化）→ 清空本轮选中
watch(
  () => game.value.round,
  () => {
    selected.value = null
  },
)

function tap(cell: Cell) {
  if (!canFire.value) return
  selected.value = cell
}

function confirmFire() {
  if (!selected.value || !canFire.value) return
  fx.play('fire')
  haptics.vibrate('fire')
  props.socket.send({ type: 'fire', row: selected.value.row, col: selected.value.col })
  selected.value = null
}

// P6 手感：出炮回包与被打中反馈（混战一轮多人同时开炮，incoming 一次可能来多发——只报最重的一次）
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
    const recent = game.value.you.incoming.slice(old).filter((x) => x.result !== 'miss')
    if (recent.length === 0) return
    const heaviest = recent.some((x) => x.result === 'head') ? 'head' : 'body'
    fx.play(heaviest)
    haptics.vibrate('inbound')
  },
)

function colLabel(c: number): string {
  return 'ABCDEFGHIJKLMNOP'[c] ?? String(c + 1)
}

function leave() {
  if (!s.roomClosed) props.socket.send({ type: 'leaveRoom' })
  props.store.resetToLobby()
}
</script>

<template>
  <section class="melee">
    <header class="bar">
      <span class="round">第 {{ game.round ?? 1 }} 轮</span>
      <Countdown v-if="!paused" :deadline-at="game.deadlineAt" />
    </header>

    <div class="tabs" role="tablist">
      <button
        type="button"
        class="tab"
        :class="{ on: focus === null }"
        role="tab"
        :aria-selected="focus === null"
        @click="focus = null"
      >
        全部
      </button>
      <button
        v-for="o in opponents"
        :key="o.playerId"
        type="button"
        class="tab"
        :class="{ on: focus === o.playerId, dead: !o.alive }"
        role="tab"
        :aria-selected="focus === o.playerId"
        @click="focus = o.playerId"
      >
        <i class="dot" :style="{ '--seat': o.color }" aria-hidden="true" />
        {{ o.nickname }}
        <span class="meta">{{ o.alive ? `${o.planesDestroyed}/${rules.planeCount}` : '出局' }}</span>
      </button>
    </div>

    <div class="board-block">
      <div class="board-title">
        <span>{{ focus === null ? '目标棋盘 · 一炮打所有人' : `只看 ${nickOf(focus)}` }}</span>
        <label v-if="rules.hintAllowed" class="hint-toggle">
          <input v-model="hintOn" type="checkbox" :disabled="focus === null" />
          推理提示
        </label>
      </div>
      <BoardGrid
        :board-size="rules.boardSize"
        :cells="targetCells"
        :disabled="!canFire"
        :selected-key="selectedKey"
        :mark-layout="focus === null ? 'merged' : 'single'"
        @cell-tap="tap"
      />
    </div>

    <button v-if="selected" class="btn primary fire-btn" @click="confirmFire">
      开炮 {{ colLabel(selected.col) }}{{ selected.row + 1 }}
    </button>
    <p v-else-if="submitted" class="muted center">已开炮，等待其他人…</p>
    <p v-else-if="iAmAlive" class="muted center">点一格选中，再按「开炮」</p>

    <div class="peers">
      <span v-for="o in aliveOpponents" :key="o.playerId" class="peer">
        <i class="dot" :style="{ '--seat': o.color }" aria-hidden="true" />
        {{ o.status }}
      </span>
    </div>

    <div class="board-block own">
      <div class="board-title">
        <span>我方海域 · 剩 {{ rules.planeCount - game.you.planesDestroyed }} 架</span>
      </div>
      <BoardGrid :board-size="rules.boardSize" :cells="ownCells" disabled />
    </div>

    <div v-if="!iAmAlive" class="out">
      <p>你已出局，可继续观看</p>
      <button class="btn ghost" @click="leave">返回大厅</button>
    </div>
  </section>
</template>

<style scoped>
.melee {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  border-radius: 12px;
  background: var(--bg-raised);
  border: 1px solid var(--grid-line);
}
.round {
  font-weight: 700;
  letter-spacing: 0.06em;
}
.tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
  -webkit-overflow-scrolling: touch;
}
.tab {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--grid-line);
  background: transparent;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.tab.on {
  border-color: var(--paper);
  background: var(--sea);
}
.tab.dead {
  opacity: 0.45;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--seat);
}
.meta {
  color: var(--ink-soft);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
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
.hint-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.own :deep(.board-wrap) {
  max-width: 240px;
}
.fire-btn {
  position: sticky;
  bottom: 12px;
  z-index: 6;
  box-shadow: 0 6px 20px rgb(0 0 0 / 0.4);
}
.peers {
  display: flex;
  gap: 12px;
  justify-content: center;
  font-size: 12px;
  color: var(--ink-soft);
}
.peer {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.center {
  text-align: center;
  margin: 0;
}
.out {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--grid-line);
  background: rgb(21 37 59 / 0.7);
}
.out p {
  margin: 0;
}
</style>
