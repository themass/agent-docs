<script setup lang="ts">
/**
 * 个人战绩页（spec §21.4）：段位详情 + 累计统计 + 最近战绩列表。
 * 数据全部来自 profile 推送；此页只读，不发新请求。
 */
import { computed } from 'vue'
import { TIERS, tierLabel } from '@plane-duel/shared'
import type { GameStore } from '../net/store'

const props = defineProps<{ store: GameStore }>()
const emit = defineEmits<{ close: [] }>()
const p = computed(() => props.store.state.profile)

const MODE_TEXT = { duel: '对决', melee: '混战' } as const
const PRESET_TEXT: Record<string, string> = { beginner: '入门', standard: '标准', advanced: '进阶', expert: '高手' }

function timeText(at: number): string {
  const d = new Date(at)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<template>
  <div v-if="p" class="overlay" role="dialog" aria-label="我的战绩">
    <div class="sheet">
      <h2>{{ TIERS[p.rank.tier] ?? tierLabel(p.rank.tier) }}</h2>
      <p class="muted">
        第 {{ p.season }} 赛季
        <template v-if="p.rank.tier < TIERS.length - 1"> · {{ p.rank.stars }} 星</template>
        <template v-else> · {{ p.rank.stars }} 星</template>
        <template v-if="p.rank.lossStreak > 0"> · <span class="warn">连败 {{ p.rank.lossStreak }}</span></template>
      </p>

      <div class="stats">
        <div class="stat"><b>{{ p.stats.wins }}</b><span class="muted">胜</span></div>
        <div class="stat"><b>{{ p.stats.losses }}</b><span class="muted">负</span></div>
        <div class="stat"><b>{{ p.stats.streak }}</b><span class="muted">连胜</span></div>
        <div class="stat"><b>{{ p.stats.totalHits }}</b><span class="muted">总命中</span></div>
      </div>
      <p class="muted small">历史最高：{{ TIERS[p.stats.bestTier] }} {{ p.stats.bestStars }} 星 · 计分 {{ p.stats.scoringGames }} 局</p>

      <ul v-if="p.recent.length" class="recent">
        <li v-for="g in p.recent" :key="g.id" :class="{ win: g.win }">
          <span class="res">{{ g.win ? '胜' : '负' }}</span>
          <span class="desc">{{ MODE_TEXT[g.mode] }}{{ g.capacity }}人 · {{ PRESET_TEXT[g.preset] }} · 第 {{ g.rank }} 名 · 命中 {{ g.hits }}</span>
          <span class="delta" :class="g.delta > 0 ? 'up' : g.delta < 0 ? 'down' : ''">
            {{ g.delta > 0 ? `+${g.delta}` : g.delta }}
          </span>
          <span class="when muted">{{ timeText(g.at) }}</span>
        </li>
      </ul>
      <p v-else class="muted small">还没有战绩。去排一局吧。</p>

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
  gap: 8px;
  padding: 20px 18px;
  border-radius: 16px;
  background: var(--bg-raised);
  border: 1px solid var(--grid-line);
  text-align: center;
}
.sheet h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 26px;
  letter-spacing: 0.14em;
  color: var(--accent);
}
.sheet p {
  margin: 0;
}
.warn {
  color: var(--kill);
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  width: 100%;
}
.stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--sea-dim);
}
.stat b {
  font-size: 18px;
}
.stat span {
  font-size: 11px;
}
.recent {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
}
.recent li {
  display: grid;
  grid-template-columns: 32px 1fr auto;
  grid-template-rows: auto auto;
  column-gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--sea-dim);
  font-size: 13px;
}
.res {
  grid-row: span 2;
  align-self: center;
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--ink-soft);
}
.win .res {
  color: var(--accent);
}
.desc {
  color: var(--ink);
}
.delta {
  align-self: center;
  font-weight: 600;
  color: var(--ink-soft);
}
.delta.up {
  color: var(--accent);
}
.delta.down {
  color: var(--kill);
}
.when {
  font-size: 11px;
}
</style>
