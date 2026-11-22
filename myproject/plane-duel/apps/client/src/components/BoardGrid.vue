<script setup lang="ts">
import type { Cell } from '@plane-duel/shared'
import type { BoardCell, TargetCell } from '../board-model'

type AnyCell = BoardCell | TargetCell

const props = defineProps<{
  boardSize: number
  /** BoardCell：自己的棋盘 / P0 对手棋盘；TargetCell：带多对手标记的目标棋盘 */
  cells: AnyCell[]
  disabled?: boolean
  /** 正在发送中的格子（乐观禁用，防止连点） */
  pendingKey?: string | null
  /** 可选的机头候选高亮（默认关闭，见 spec §十二） */
  hintKeys?: Set<string>
  /** 两步开炮：已选中、待确认的格子 */
  selectedKey?: string | null
  /** 标记布局：merged = 2×2 小槽（合并视图）；single = 单个大标记（focus 视图） */
  markLayout?: 'merged' | 'single'
}>()

const emit = defineEmits<{ cellTap: [cell: Cell] }>()

const keyOf = (c: AnyCell) => `${c.row},${c.col}`

/** 该格是否已被打过：TargetCell 看 fired，BoardCell 看 state。 */
const isFired = (c: AnyCell) => ('fired' in c ? c.fired : c.state !== 'unknown')
const marksOf = (c: AnyCell) => ('marks' in c ? c.marks : [])
const isHint = (c: AnyCell) => ('hint' in c ? c.hint : (props.hintKeys?.has(keyOf(c)) ?? false))
const cellState = (c: AnyCell) => ('state' in c ? c.state : '')

function onTap(c: AnyCell) {
  if (props.disabled) return
  if (isFired(c)) return
  if (props.pendingKey === keyOf(c)) return
  emit('cellTap', { row: c.row, col: c.col })
}

const COLS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
</script>

<template>
  <div class="board-wrap">
    <div class="col-labels" :style="{ '--n': boardSize }">
      <span v-for="i in boardSize" :key="i">{{ COLS[i - 1] }}</span>
    </div>
    <div class="board-row">
      <div class="row-labels" :style="{ '--n': boardSize }">
        <span v-for="i in boardSize" :key="i">{{ i }}</span>
      </div>
      <div class="board" :style="{ '--n': boardSize }" role="grid" aria-label="棋盘">
        <button
          v-for="c in cells"
          :key="keyOf(c)"
          type="button"
          class="cell"
          :class="[
            cellState(c),
            {
              disabled: disabled || isFired(c),
              pending: pendingKey === keyOf(c),
              selected: selectedKey === keyOf(c),
              hint: isHint(c) && !isFired(c),
              'target-fired': 'fired' in c && c.fired,
            },
          ]"
          :aria-label="`${COLS[c.col]}${c.row + 1}`"
          :aria-pressed="selectedKey === keyOf(c)"
          @click="onTap(c)"
        >
          <span
            v-if="marksOf(c).length"
            class="marks"
            :class="markLayout === 'single' ? 'single' : 'merged'"
          >
            <i
              v-for="m in marksOf(c)"
              :key="m.playerId"
              class="mark"
              :class="[m.result, { dim: m.dim }]"
              :style="{ '--seat': m.color }"
            />
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.board-wrap {
  width: 100%;
  max-width: 420px;
  margin: 0 auto;
  user-select: none;
  -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.col-labels,
.row-labels {
  display: grid;
  font-size: 10px;
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}

.col-labels {
  grid-template-columns: repeat(var(--n), 1fr);
  margin-left: 18px;
  margin-bottom: 3px;
  text-align: center;
}

.board-row {
  display: flex;
  gap: 4px;
}

.row-labels {
  grid-template-rows: repeat(var(--n), 1fr);
  width: 14px;
  align-items: center;
  text-align: right;
}

.board {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(var(--n), 1fr);
  gap: 2px;
  aspect-ratio: 1;
  padding: 2px;
  background: var(--grid-line);
  border-radius: 4px;
}

.cell {
  aspect-ratio: 1;
  border: 0;
  padding: 0;
  border-radius: 2px;
  background: var(--sea);
  cursor: pointer;
  position: relative;
  transition: transform 80ms ease, background-color 120ms ease;
}

.cell:not(.disabled):active {
  transform: scale(0.88);
}

.cell.disabled {
  cursor: default;
}

.cell.miss {
  background: var(--sea-dim);
}

.cell.miss::after {
  content: '';
  position: absolute;
  inset: 38%;
  border-radius: 50%;
  background: var(--ink-soft);
  opacity: 0.55;
}

.cell.body {
  background: var(--hit);
  animation: cell-pop 180ms ease-out;
}

.cell.head {
  background: var(--kill);
  animation: cell-pop 240ms cubic-bezier(0.2, 1.4, 0.4, 1);
}

/* P6 手感：命中/击落的爆点缩放（新格子挂载即触发） */
@keyframes cell-pop {
  from {
    transform: scale(0.55);
    filter: brightness(2.2);
  }
  to {
    transform: scale(1);
    filter: brightness(1);
  }
}

.cell.head::after {
  content: '';
  position: absolute;
  inset: 22%;
  border-radius: 50%;
  border: 2px solid var(--paper);
}

.cell.pending {
  background: var(--pending);
  animation: pulse 0.6s ease-in-out infinite alternate;
}

.cell.hint {
  outline: 1.5px dashed var(--hit);
  outline-offset: -3px;
}

.cell.selected {
  outline: 2px solid var(--paper);
  outline-offset: -2px;
  background: var(--pending);
}

.cell.target-fired {
  background: var(--sea-dim);
}

/* 多对手标记：合并视图 2×2 小槽，focus 视图单个大标记 */
.marks {
  position: absolute;
  inset: 0;
  display: grid;
  pointer-events: none;
}

.marks.merged {
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  padding: 12%;
  gap: 8%;
}

.marks.single {
  place-items: center;
}

.mark {
  display: block;
  box-sizing: border-box;
  border-radius: 50%;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
}

.marks.single .mark {
  width: 64%;
  height: 64%;
}

/* miss：空心小环；body：实心；head：实心外加白色描边 */
.mark.miss {
  border: 2px solid var(--seat);
  opacity: 0.55;
  transform: scale(0.7);
}

.mark.body {
  background: var(--seat);
}

.mark.head {
  background: var(--seat);
  box-shadow: 0 0 0 2px var(--paper);
}

.mark.dim {
  opacity: 0.3;
}

@keyframes pulse {
  from { opacity: 0.55; }
  to { opacity: 1; }
}
</style>
