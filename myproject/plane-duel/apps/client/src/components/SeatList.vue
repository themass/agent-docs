<script setup lang="ts">
/** 等候室座位表：座位色、昵称（电脑带 🤖）、准备 ✓、掉线、房主、空座、房主移出未准备者。 */
import { ref, watch } from 'vue'
import type { SeatView, TableView } from '@plane-duel/shared'
import { SEAT_COLORS } from '../board-model'
import { canKick, seatLabel } from '../lobby-model'

const props = defineProps<{
  seats: (SeatView | null)[]
  hostId: string | null
  youId: string | null
  /** 当前完整牌桌视图；传入时才显示"移出"按钮 */
  table?: TableView | null
}>()
const emit = defineEmits<{ kick: [playerId: string] }>()

/** 两步确认（原生 confirm 在部分内嵌 webview 里会卡住，页面内自己做） */
const pendingKick = ref<string | null>(null)
watch(() => props.seats.map((x) => x?.playerId).join(','), () => (pendingKick.value = null))

function kickTap(playerId: string) {
  if (pendingKick.value === playerId) {
    pendingKick.value = null
    emit('kick', playerId)
  } else {
    pendingKick.value = playerId
  }
}
</script>

<template>
  <ul class="seats">
    <li
      v-for="(seat, i) in seats"
      :key="i"
      class="seat"
      :class="{ empty: !seat }"
      :style="{ '--seat': SEAT_COLORS[i % SEAT_COLORS.length] }"
    >
      <span class="dot" aria-hidden="true" />
      <template v-if="seat">
        <span class="nick">
          {{ seatLabel(seat) }}<span v-if="seat.playerId === youId" class="muted">（你）</span>
        </span>
        <span v-if="seat.playerId === hostId" class="tag">房主</span>
        <span v-if="!seat.connected" class="tag warn">掉线</span>
        <span class="state" :class="{ ok: seat.ready }">{{ seat.ready ? '✓ 已准备' : '未准备' }}</span>
        <button
          v-if="table && youId && canKick(table, youId, seat)"
          type="button"
          class="kick"
          :class="{ confirm: pendingKick === seat.playerId }"
          @click="kickTap(seat.playerId)"
        >
          {{ pendingKick === seat.playerId ? '确认移出？' : '移出' }}
        </button>
      </template>
      <template v-else>
        <span class="nick muted">等待加入…</span>
      </template>
    </li>
  </ul>
</template>

<style scoped>
.seats {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.seat {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--sea-dim);
  border: 1px solid var(--grid-line);
  font-size: 15px;
}
.seat.empty {
  border-style: dashed;
  background: transparent;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--seat);
  flex: none;
}
.seat.empty .dot {
  background: var(--grid-line);
}
.nick {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tag {
  flex: none;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid var(--grid-line);
  color: var(--ink-soft);
}
.tag.warn {
  color: var(--kill);
  border-color: var(--kill);
}
.state {
  flex: none;
  font-size: 12px;
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}
.state.ok {
  color: var(--ok);
}
.kick {
  flex: none;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid var(--kill);
  background: transparent;
  color: var(--kill);
  font-size: 12px;
  cursor: pointer;
}
.kick.confirm {
  background: var(--kill);
  color: var(--bg-raised);
}
.muted {
  color: var(--ink-soft);
}
</style>
