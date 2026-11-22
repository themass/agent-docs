<script setup lang="ts">
/**
 * 等候室：房间号（可复制）、座位表、规则摘要、准备 / 修改规则 / 离开。
 *
 * 好友房人满且全员准备才开局；匹配房首局人齐自动开局，之后"再来一局"= 准备。
 */
import { computed, ref } from 'vue'
import RuleEditor from '../components/RuleEditor.vue'
import SeatList from '../components/SeatList.vue'
import { hasBots } from '../lobby-model'
import { ruleSummary } from '../rule-editor-model'
import type { RuleSet } from '@plane-duel/shared'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const s = props.store.state
const emit = defineEmits<{ back: [] }>()

const editing = ref(false)

const table = computed(() => s.table)
const youId = computed(() => s.playerId)
const mySeat = computed(() => table.value?.seats.find((x) => x?.playerId === youId.value) ?? null)
const isHost = computed(() => table.value !== null && table.value.hostId === youId.value)
const canEditRules = computed(() => isHost.value && table.value?.kind === 'friend')
const ready = computed(() => mySeat.value?.ready ?? false)
const isPractice = computed(() => table.value?.kind === 'practice')
const withBots = computed(() => (table.value ? hasBots(table.value) : false))

function toggleReady() {
  props.socket.send({ type: 'setReady', ready: !ready.value, rulesVersion: table.value?.rulesVersion ?? 0 })
}

function toggleListed() {
  if (table.value === null) return
  props.socket.send({ type: 'setListed', listed: !table.value.listed })
}

function kick(playerId: string) {
  props.socket.send({ type: 'kick', playerId })
}

function saveRules(rules: RuleSet) {
  editing.value = false
  props.socket.send({ type: 'updateRules', rules })
}

function leave() {
  // 服务端不会给离开者回任何消息，客户端自行复位
  props.socket.send({ type: 'leaveRoom' })
  props.store.resetToLobby()
  emit('back')
}

async function copyCode() {
  if (!table.value) return
  try {
    await navigator.clipboard?.writeText(table.value.roomCode)
    s.error = '房间号已复制'
  } catch {
    // 剪贴板不可用就什么也不做
  }
}
</script>

<template>
  <section v-if="table" class="waiting">
    <header v-if="isPractice" class="code-block">
      <div class="label">人机练习</div>
      <div class="practice-title">练习 · 不计段位</div>
    </header>
    <header v-else class="code-block">
      <div class="label">房间号</div>
      <button type="button" class="code" :aria-label="`复制房间号 ${table.roomCode}`" @click="copyCode">
        {{ table.roomCode }}
      </button>
      <div class="muted small">点房间号复制，发给朋友一起玩</div>
    </header>

    <p v-if="withBots" class="bots-note">本桌有电脑 🤖<span v-if="table.kind === 'match'"> · 对局不计段位</span></p>

    <SeatList :seats="table.seats" :host-id="table.hostId" :you-id="youId" :table="table" @kick="kick" />

    <div class="card">
      <h2>规则</h2>
      <p class="summary">{{ ruleSummary(table.rules) }}</p>
      <button v-if="canEditRules && !editing" type="button" class="btn ghost" @click="editing = true">
        修改规则
      </button>
      <RuleEditor v-if="editing" :rules="table.rules" submit-label="保存规则" @submit="saveRules" />
      <label v-if="isHost && table.kind === 'friend'" class="listed-row">
        <span>公开到房间列表</span>
        <input type="checkbox" class="switch" :checked="table.listed" @change="toggleListed" />
      </label>
    </div>

    <button type="button" class="btn" :class="ready ? 'ghost' : 'primary'" @click="toggleReady">
      {{ ready ? '取消准备' : '准备' }}
    </button>
    <button type="button" class="btn ghost" @click="leave">离开房间</button>
  </section>
</template>

<style scoped>
.waiting {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.code-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 0;
}
.label {
  font-size: 11px;
  color: var(--ink-soft);
  letter-spacing: 0.14em;
}
.code {
  border: 0;
  background: none;
  padding: 0 4px;
  font-family: var(--font-display);
  font-size: 38px;
  letter-spacing: 0.2em;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
  cursor: pointer;
}
.code:active {
  color: var(--accent);
}
.practice-title {
  font-family: var(--font-display);
  font-size: 24px;
  letter-spacing: 0.14em;
}
.bots-note {
  margin: 0;
  text-align: center;
  font-size: 13px;
  color: var(--accent);
}
.listed-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  cursor: pointer;
}
.listed-row .switch {
  width: 22px;
  height: 22px;
  accent-color: var(--accent);
  cursor: pointer;
}
.small {
  font-size: 12px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 14px;
  background: rgb(21 37 59 / 0.7);
  border: 1px solid var(--grid-line);
}
.card h2 {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.1em;
  color: var(--ink-soft);
}
.summary {
  margin: 0;
  letter-spacing: 0.04em;
}
</style>
