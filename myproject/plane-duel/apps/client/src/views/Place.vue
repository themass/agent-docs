<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Cell } from '@plane-duel/shared'
import { cellKey } from '@plane-duel/shared'
import BoardGrid from '../components/BoardGrid.vue'
import Countdown from '../components/Countdown.vue'
import { buildBoardCells } from '../board-model'
import { togglePlane } from '../place-model'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const s = props.store.state

const rules = computed(() => s.table!.rules)
const game = computed(() => s.game)

/** 本地草稿：点格子即时反馈，放满后点「就绪」才提交 */
const heads = ref<Cell[]>([])
const accepted = ref(false)

// 重开一局（新对局视图）时清空草稿
watch(
  () => game.value?.you.planes,
  (planes) => {
    if (planes && planes.length > 0) {
      accepted.value = true
      heads.value = planes
    }
  },
)

const cells = computed(() =>
  buildBoardCells({
    boardSize: rules.value.boardSize,
    shots: [],
    planes: heads.value,
    showPlane: true,
  }),
)

const full = computed(() => heads.value.length >= rules.value.planeCount)
const paused = computed(() => game.value?.phase === 'paused')

const ERRORS = {
  edge: '机头不能放在边缘一圈，飞机要完整落在海域内',
  overlap: '飞机不能重叠',
  full: '已放满了，点已有的飞机可以移除',
} as const

function place(cell: Cell) {
  if (paused.value) return
  const r = togglePlane(heads.value, cell, rules.value)
  heads.value = r.heads
  accepted.value = false
  if (r.error) s.error = ERRORS[r.error]
}

function ready() {
  if (!full.value) return
  props.socket.send({ type: 'placePlane', planes: heads.value })
}

const hint = computed(() => {
  if (accepted.value) return { text: '已就绪，等待其他玩家…', ok: true }
  if (full.value) return { text: '点「就绪」提交摆放；点机身可移除重摆', ok: false }
  return {
    text: `点一格放机头（${heads.value.length}/${rules.value.planeCount}）`,
    ok: false,
  }
})

function leave() {
  props.socket.send({ type: 'leaveRoom' })
  props.store.resetToLobby()
}
</script>

<template>
  <section class="place">
    <header class="bar">
      <div>
        <div class="label">房间号</div>
        <div class="code">{{ s.table?.roomCode }}</div>
      </div>
      <div class="right">
        <div class="label">摆放剩余</div>
        <Countdown v-if="!paused" :deadline-at="game?.deadlineAt ?? null" />
        <span v-else class="muted">已暂停</span>
      </div>
    </header>

    <p class="hint" :class="{ ok: hint.ok }">{{ hint.text }}</p>

    <BoardGrid
      :board-size="rules.boardSize"
      :cells="cells"
      :disabled="paused || accepted"
      @cell-tap="place"
    />

    <p v-if="paused" class="muted center">对手已掉线，计时已暂停</p>

    <button v-if="!accepted" class="btn primary" :disabled="!full" @click="ready">就绪</button>
    <button class="btn ghost" @click="leave">离开房间</button>
  </section>
</template>

<style scoped>
.place {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
.label {
  font-size: 11px;
  color: var(--ink-soft);
  letter-spacing: 0.12em;
}
.code {
  font-family: var(--font-display);
  font-size: 26px;
  letter-spacing: 0.18em;
  font-variant-numeric: tabular-nums;
}
.right {
  text-align: right;
}
.hint {
  margin: 0;
  text-align: center;
}
.hint.ok {
  color: var(--ok);
}
.center {
  text-align: center;
}
</style>
