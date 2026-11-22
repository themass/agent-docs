<script setup lang="ts">
/**
 * 金币条（spec §廿二.7）：大厅入口。余额 + 账本页入口。
 * v4 服务端不下发 coins 字段时 profile.coins 缺省——余额 0 也照常显示，
 * 因为登录礼会让它立刻变 50。
 */
import type { GameStore } from '../net/store'

const props = defineProps<{ store: GameStore }>()
const s = props.store.state

const emit = defineEmits<{ open: [] }>()
</script>

<template>
  <button type="button" class="coin-bar" @click="emit('open')">
    <span class="coin" aria-hidden="true">◎</span>
    <span class="num">{{ s.coins }}</span>
    <span class="go" aria-hidden="true">›</span>
  </button>
</template>

<style scoped>
.coin-bar {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--grid-line);
  background: rgb(21 37 59 / 0.7);
  color: var(--ink);
  font-size: 14px;
  cursor: pointer;
}
.coin-bar:hover {
  border-color: var(--pending);
}
.coin {
  color: var(--accent);
  font-size: 16px;
}
.num {
  font-family: var(--font-display);
  letter-spacing: 0.04em;
}
.go {
  color: var(--ink-soft);
}
</style>
