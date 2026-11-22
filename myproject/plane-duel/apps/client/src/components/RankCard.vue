<script setup lang="ts">
/**
 * 段位卡（spec §21.2）：大厅入口。显示段位名 + 星数 + 赛季号，
 * 点开进个人战绩页；旁边带段位榜入口。v3 服务端不下发 profile 时整卡隐藏。
 */
import { computed } from 'vue'
import { starCap, TIERS } from '@plane-duel/shared'
import type { GameStore } from '../net/store'

const props = defineProps<{ store: GameStore }>()
const s = props.store.state

const p = computed(() => s.profile)
const tierText = computed(() => (p.value ? TIERS[p.value.rank.tier] ?? `段位${p.value.rank.tier}` : ''))
const isMarshal = computed(() => (p.value?.rank.tier ?? 0) >= TIERS.length - 1)
const cap = computed(() => (p.value ? starCap(p.value.rank.tier) : 0))

const emit = defineEmits<{ open: []; rankList: [] }>()
</script>

<template>
  <div v-if="p" class="rank-card">
    <button type="button" class="card-main" @click="emit('open')">
      <span class="tier">{{ tierText }}</span>
      <span v-if="!isMarshal" class="stars" :aria-label="`${p.rank.stars} 星`">
        <span v-for="i in cap" :key="i" class="star" :class="{ on: i <= p.rank.stars }" aria-hidden="true" />
      </span>
      <span v-else class="stars marshal">{{ p.rank.stars }} 星</span>
      <span class="meta muted">第 {{ p.season }} 赛季 · {{ p.stats.wins }} 胜</span>
      <span class="go" aria-hidden="true">›</span>
    </button>
    <button type="button" class="board-btn" @click="emit('rankList')">段位榜</button>
  </div>
</template>

<style scoped>
.rank-card {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.card-main {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
  padding: 12px 36px 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--grid-line);
  background: rgb(21 37 59 / 0.7);
  text-align: left;
  cursor: pointer;
  color: var(--ink);
}
.card-main:hover {
  border-color: var(--pending);
}
.tier {
  font-family: var(--font-display);
  font-size: 18px;
  letter-spacing: 0.1em;
  color: var(--accent);
}
.stars {
  display: flex;
  gap: 4px;
}
.stars.marshal {
  font-size: 13px;
  color: var(--ink-soft);
}
.star {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid var(--pending);
  background: transparent;
}
.star.on {
  background: var(--pending);
}
.meta {
  font-size: 12px;
}
.go {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 20px;
  color: var(--ink-soft);
}
.board-btn {
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid var(--grid-line);
  background: rgb(21 37 59 / 0.7);
  color: var(--ink-soft);
  font-size: 13px;
  cursor: pointer;
}
.board-btn:hover {
  border-color: var(--pending);
  color: var(--ink);
}
</style>
