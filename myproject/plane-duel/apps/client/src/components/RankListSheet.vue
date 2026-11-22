<script setup lang="ts">
/**
 * 段位榜弹层（spec §21.5）：请求-响应 + 30 秒缓存自刷。
 * 打开即拉一次；缓存超过 30 秒再点刷新。榜单条目没有 playerId（隐私）。
 */
import { computed, onMounted } from 'vue'
import { TIERS } from '@plane-duel/shared'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const emit = defineEmits<{ close: [] }>()
const s = props.store.state

const RANK_LIST_TTL_MS = 30_000

const rl = computed(() => s.rankList)
const stale = computed(() => rl.value === null || Date.now() - rl.value.at >= RANK_LIST_TTL_MS)

function refresh() {
  props.socket.send({ type: 'rankListRequest' })
}

// 打开即拉一次；30 秒内的缓存直接展示（§21.5 客户端自刷）
onMounted(() => {
  if (stale.value) refresh()
})
</script>

<template>
  <div class="overlay" role="dialog" aria-label="段位榜">
    <div class="sheet">
      <div class="head">
        <h2>段位榜 <span class="muted small">第 {{ rl?.season ?? '…' }} 赛季</span></h2>
        <button type="button" class="refresh" :disabled="!stale" @click="refresh">
          {{ rl === null ? '加载中…' : stale ? '刷新' : '刚刚更新' }}
        </button>
      </div>

      <ol v-if="rl && rl.entries.length" class="rows">
        <li v-for="e in rl.entries" :key="e.pos" :class="{ top: e.pos <= 3, me: e.nickname === s.nickname }">
          <span class="pos">{{ e.pos }}</span>
          <span class="nick">{{ e.nickname }}</span>
          <span class="tier">{{ TIERS[e.tier] }} {{ e.stars }}★</span>
          <span class="wins muted">{{ e.wins }} 胜</span>
        </li>
      </ol>
      <p v-else-if="rl" class="muted">本赛季还没有计分局上榜。打赢一局不计电脑的对局就能上榜。</p>
      <p v-else class="muted">正在加载榜单…</p>

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
.refresh {
  background: none;
  border: 0;
  color: var(--ink-soft);
  font-size: 13px;
  cursor: pointer;
}
.refresh:disabled {
  cursor: default;
  opacity: 0.6;
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
  grid-template-columns: 32px 1fr auto auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--sea-dim);
  font-size: 14px;
}
.rows li.top .pos {
  color: var(--pending);
}
.rows li.me {
  outline: 1px solid var(--pending);
}
.pos {
  font-family: var(--font-display);
  color: var(--ink-soft);
  text-align: center;
}
.nick {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tier {
  font-size: 12px;
  color: var(--accent);
}
.wins {
  font-size: 12px;
}
</style>
