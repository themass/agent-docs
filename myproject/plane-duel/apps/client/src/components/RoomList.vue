<script setup lang="ts">
/**
 * 公开房间列表（spec §20.6）：订阅由 Zone 负责，这里只渲染行与转发点击。
 * 行文案全部来自 lobby-model.roomListRows——这里不做任何折算，保证可单测的都在纯函数里。
 */
import { computed } from 'vue'
import type { RoomListEntry } from '@plane-duel/shared'
import { roomListRows } from '../lobby-model'

const props = defineProps<{ entries: RoomListEntry[] | null }>()
const emit = defineEmits<{ join: [tableId: string] }>()

const rows = computed(() => roomListRows(props.entries ?? []))
</script>

<template>
  <ul class="rooms">
    <li v-for="row in rows" :key="row.tableId">
      <button type="button" class="room" :disabled="row.full" @click="emit('join', row.tableId)">
        <span class="room-title">{{ row.title }}</span>
        <span class="room-summary muted">{{ row.summary }}</span>
        <span class="room-seats" :class="{ full: row.full }">{{ row.seatsText }}</span>
      </button>
    </li>
    <li v-if="rows.length === 0" class="empty muted">暂时没有公开的房间，创建一个吧</li>
  </ul>
</template>

<style scoped>
.rooms {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.room {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-areas: 'title seats' 'summary seats';
  align-items: center;
  gap: 2px 12px;
  width: 100%;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--grid-line);
  background: var(--sea-dim);
  text-align: left;
  cursor: pointer;
  transition: border-color 120ms ease;
}
.room:hover:not(:disabled) {
  border-color: var(--pending);
}
.room:disabled {
  opacity: 0.5;
  cursor: default;
}
.room-title {
  grid-area: title;
  font-size: 15px;
}
.room-summary {
  grid-area: summary;
  font-size: 12px;
}
.room-seats {
  grid-area: seats;
  font-variant-numeric: tabular-nums;
  color: var(--accent);
}
.room-seats.full {
  color: var(--ink-soft);
}
.empty {
  padding: 10px 4px;
  font-size: 13px;
  text-align: center;
}
</style>
