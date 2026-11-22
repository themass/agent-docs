<script setup lang="ts">
import { ref } from 'vue'
import { sanitizeNickname } from '@plane-duel/shared'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'
import { saveNickname } from '../net/socket'
import RankCard from '../components/RankCard.vue'
import CoinBar from '../components/CoinBar.vue'
import { fx } from '../fx/fx'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const s = props.store.state

const code = ref('')
const editingNick = ref(false)
const nickDraft = ref('')
// P6：大厅的静音开关（全局持久化在 fx 单例里）
const muted = ref(fx.muted)

const emit = defineEmits<{
  zone: [capacity: 2 | 3 | 4]
  profile: []
  rankList: []
  coin: []
}>()

function joinRoom() {
  const c = code.value.trim()
  if (!/^\d{6}$/.test(c)) {
    s.error = '请输入 6 位数字房间号'
    return
  }
  props.socket.send({ type: 'joinRoom', roomCode: c })
}

function onCodeInput(e: Event) {
  code.value = (e.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 6)
}

function startEditNick() {
  nickDraft.value = s.nickname
  editingNick.value = true
}

function commitNick() {
  editingNick.value = false
  const name = sanitizeNickname(nickDraft.value, '')
  if (!name || name === s.nickname) return
  s.nickname = name
  saveNickname(name)
  props.socket.send({ type: 'setNickname', nickname: name })
}

const ZONES = [
  { capacity: 2 as const, title: '2 人对决', sub: '轮流开炮 · 先击落对方机头者胜' },
  { capacity: 3 as const, title: '3 人混战', sub: '同时开炮 · 一炮打所有人' },
  { capacity: 4 as const, title: '4 人混战', sub: '同时开炮 · 最后存活者胜' },
]
</script>

<template>
  <section class="lobby">
    <header class="hero">
      <div class="emblem" aria-hidden="true">
        <span v-for="i in 9" :key="i" :class="{ head: i === 5 }" />
      </div>
      <h1>飞机对决</h1>
      <button v-if="!editingNick" type="button" class="nick-btn" @click="startEditNick">
        {{ s.nickname || '…' }} <span class="muted small">改名</span>
      </button>
      <div v-else class="nick-edit">
        <input
          v-model="nickDraft"
          class="nick-input"
          maxlength="12"
          aria-label="昵称"
          @keyup.enter="commitNick"
        />
        <button type="button" class="btn primary nick-ok" @click="commitNick">好</button>
      </div>
    </header>

    <RankCard :store="props.store" @open="emit('profile')" @rank-list="emit('rankList')" />

    <div class="coin-row">
      <CoinBar :store="props.store" @open="emit('coin')" />
      <button
        type="button"
        class="sound-btn"
        :aria-label="muted ? '开启音效' : '静音'"
        :aria-pressed="muted"
        @click="muted = !muted; fx.setMuted(muted)"
      >
        {{ muted ? '🔇' : '🔊' }}
      </button>
    </div>

    <button
      v-for="z in ZONES"
      :key="z.capacity"
      type="button"
      class="zone-card"
      @click="fx.play('tap'); emit('zone', z.capacity)"
    >
      <span class="zone-title">{{ z.title }}</span>
      <span class="zone-sub muted">{{ z.sub }}</span>
      <span class="zone-go" aria-hidden="true">›</span>
    </button>

    <div class="card">
      <div class="divider"><span>或输入房间号</span></div>
      <input
        class="input"
        inputmode="numeric"
        maxlength="6"
        placeholder="6 位房间号"
        :value="code"
        aria-label="房间号"
        @input="onCodeInput"
        @keyup.enter="joinRoom"
      />
      <button type="button" class="btn" :disabled="code.length !== 6" @click="joinRoom">加入好友房</button>
    </div>
  </section>
</template>

<style scoped>
.lobby {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hero {
  text-align: center;
  padding: 20px 0 4px;
}
.hero h1 {
  font-family: var(--font-display);
  font-size: 34px;
  letter-spacing: 0.12em;
  margin: 12px 0 4px;
}
.emblem {
  display: inline-grid;
  grid-template-columns: repeat(3, 14px);
  gap: 3px;
}
.emblem span {
  width: 14px;
  height: 14px;
  border-radius: 2px;
  background: var(--hit);
}
.emblem span.head {
  background: var(--kill);
}
.nick-btn {
  background: none;
  border: 0;
  padding: 4px 8px;
  font-size: 14px;
  color: var(--ink-soft);
  cursor: pointer;
}
.small {
  font-size: 12px;
}
.nick-edit {
  display: flex;
  gap: 8px;
  max-width: 280px;
  margin: 0 auto;
}
.nick-input {
  flex: 1;
  min-width: 0;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--grid-line);
  background: var(--sea-dim);
  color: var(--ink);
  font-size: 15px;
}
.nick-ok {
  width: auto;
  padding: 8px 16px;
  font-size: 14px;
}
.coin-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
}
.sound-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  border-radius: 999px;
  border: 1px solid var(--grid-line);
  background: var(--bg-raised);
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  box-shadow: var(--ring);
}
.zone-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
  width: 100%;
  padding: 16px 40px 16px 16px;
  border-radius: 14px;
  border: 1px solid var(--grid-line);
  background: rgb(21 37 59 / 0.7);
  text-align: left;
  cursor: pointer;
  transition: border-color 120ms ease, transform 80ms ease;
}
.zone-card:active {
  transform: scale(0.99);
}
.zone-card:hover {
  border-color: var(--pending);
}
.zone-title {
  font-family: var(--font-display);
  font-size: 22px;
  letter-spacing: 0.08em;
}
.zone-sub {
  font-size: 13px;
}
.zone-go {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 24px;
  color: var(--ink-soft);
}
.card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 14px;
  background: rgb(21 37 59 / 0.7);
  border: 1px solid var(--grid-line);
}
.divider {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-soft);
  font-size: 12px;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--grid-line);
}
</style>
