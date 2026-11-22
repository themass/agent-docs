<script setup lang="ts">
/**
 * 金币账本页（spec §廿二.7）：打开即 coinRequest 拉快照，流水倒序、收入绿/支出红。
 * 底部显示当日配额余量（§廿二.2），让玩家对"今天还能拿多少"有数。
 */
import { computed, onMounted } from 'vue'
import { COIN, COIN_REASON_LABELS } from '@plane-duel/shared'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const emit = defineEmits<{ close: [] }>()
const s = props.store.state

const cl = computed(() => s.coinLedger)
const daily = computed(() => cl.value?.daily ?? null)

function refresh() {
  props.socket.send({ type: 'coinRequest' })
}

function hhmm(at: number): string {
  const d = new Date(at)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// 打开即拉（账本变动服务端只推余额，明细要靠快照）
onMounted(refresh)
</script>

<template>
  <div class="overlay" role="dialog" aria-label="金币账本">
    <div class="sheet">
      <div class="head">
        <h2>金币</h2>
        <span class="bal">◎ {{ cl?.balance ?? s.coins }}</span>
      </div>

      <ul v-if="cl && cl.entries.length" class="rows">
        <li v-for="e in cl.entries" :key="e.id" :class="{ gain: e.delta > 0 }">
          <span class="why">{{ COIN_REASON_LABELS[e.reason] }}</span>
          <span class="when muted">{{ hhmm(e.at) }}</span>
          <span class="delta" :class="e.delta > 0 ? 'up' : 'down'">{{ e.delta > 0 ? `+${e.delta}` : e.delta }}</span>
        </li>
      </ul>
      <p v-else-if="cl" class="muted">还没有金币流水。</p>
      <p v-else class="muted">正在加载账本…</p>

      <div v-if="daily" class="caps muted small">
        <span>完成对局 {{ daily.gameGrants }}/{{ COIN.DAILY_GAME_MAX }}</span>
        <span>门票局 {{ daily.ticketPlays }}/{{ COIN.DAILY_TICKET_MAX }}</span>
        <span>今日净增 {{ Math.max(daily.netGain, 0) }}/{{ COIN.NET_GAIN_MAX }}</span>
      </div>

      <button type="button" class="btn ghost" @click="refresh">刷新</button>
      <button class="btn primary" @click="emit('close')">关闭</button>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgb(6 12 22 / 0.72);
  backdrop-filter: blur(3px);
}
.sheet {
  width: 100%;
  max-width: 360px;
  max-height: 82vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px 18px;
  border-radius: 16px;
  background: var(--bg-raised);
  border: 1px solid var(--grid-line);
}
.head {
  width: 100%;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.head h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: 0.12em;
}
.bal {
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--accent);
}
.rows {
  list-style: none;
  margin: 0;
  padding: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rows li {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--sea-dim);
  font-size: 14px;
}
.why {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.when {
  font-size: 12px;
}
.delta {
  font-family: var(--font-display);
  min-width: 44px;
  text-align: right;
}
.delta.up {
  color: var(--accent);
}
.delta.down {
  color: var(--kill);
}
.caps {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
}
.small {
  font-size: 12px;
}
</style>
