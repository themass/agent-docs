<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { fx, haptics } from '../fx/fx'

const props = defineProps<{ deadlineAt: number | null }>()
const remaining = ref<number | null>(null)

const compute = () => {
  const prev = remaining.value
  remaining.value =
    props.deadlineAt === null ? null : Math.max(0, Math.ceil((props.deadlineAt - Date.now()) / 1000))
  // P6 手感：最后 3 秒逐秒滴答（跨秒才响一次）
  if (prev !== null && remaining.value !== null && remaining.value !== prev && remaining.value <= 3 && remaining.value > 0) {
    fx.play('tick')
    haptics.vibrate('tick')
  }
}

compute()
const timer = setInterval(compute, 250)
watch(() => props.deadlineAt, compute)
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <span class="countdown" :class="{ urgent: remaining !== null && remaining <= 5 }">
    {{ remaining === null ? '--' : `${remaining}s` }}
  </span>
</template>

<style scoped>
.countdown {
  font-family: var(--font-display);
  font-variant-numeric: tabular-nums;
  font-size: 18px;
  min-width: 3ch;
  display: inline-block;
  text-align: right;
}
.urgent {
  color: var(--kill);
  animation: cd-pulse 0.5s ease-in-out infinite alternate;
}
@keyframes cd-pulse {
  from {
    transform: scale(1);
  }
  to {
    transform: scale(1.18);
  }
}
</style>
